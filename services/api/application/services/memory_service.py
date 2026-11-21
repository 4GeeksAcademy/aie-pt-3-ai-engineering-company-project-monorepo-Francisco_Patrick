"""Application service orchestrating Agent Memory extraction, intent classification, recall, and consolidation.

Implements:
- `extract_memory_candidate`: Single-turn candidate self-evaluation (< 100ms, zero secondary LLMs) (T012, FR-008)
- `UserIntentClassifier`: Explicit structured intent classification (`approve`, `reject`, `edit`,
  `unrelated_or_ambiguous`) with safe default discard and multi-intent residual query extraction (T019, FR-011, FR-013, FR-015)
- `AgentMemoryService`:
  - Single active pending proposal queue enforcement per thread/session (T020, FR-012)
  - Immutable lifecycle audit logging via `MemoryAuditLogRepositoryPort` (T023, FR-014)
  - Cross-session operational memory recall (T027, FR-006, FR-007)
  - Anti-poisoning guardrail enforcement (T034, FR-005, FR-017)
  - Carrier + Country profile consolidation and 14-day incident TTL eviction (T035, T036, FR-016)
"""

from datetime import datetime, timedelta, timezone
import re
import threading
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from application.services.memory_guardrails import (
    MemoryGuardrailValidator,
    mask_sensitive_pii,
)
from domain.agent.entities import (
    ConsolidatedCarrierProfile,
    MemoryAuditLogEntry,
    MemoryCategory,
    MemoryProposal,
    PersistentMemoryRecord,
    UserIntentClassification,
)
from domain.agent.exceptions import (
    MemoryGuardrailViolationError,
    MemoryNotFoundError,
)
from domain.agent.ports import (
    AgentMemoryRepositoryPort,
    MemoryAuditLogRepositoryPort,
    MemoryGuardrailPort,
    UserIntentClassifierPort,
)

DEFAULT_INCIDENT_TTL_DAYS = 14
PROPOSAL_CONFIRMATION_PROMPT_EN = (
    "Would you like me to remember this rule for future sessions?"
)
PROPOSAL_CONFIRMATION_PROMPT_ES = (
    "¿Te gustaría que recuerde esta regla para futuras sesiones? "
    "(Would you like me to remember this rule for future sessions?)"
)

_KNOWN_CARRIERS: Tuple[Tuple[str, str], ...] = (
    ("seur", "SEUR"),
    ("fedex", "FedEx"),
    ("gls", "GLS"),
    ("dhl", "DHL"),
    ("ups", "UPS"),
    ("correos", "Correos"),
    ("mrw", "MRW"),
    ("usps", "USPS"),
    ("ontrac", "OnTrac"),
    ("lasership", "LaserShip"),
)

_ES_REGION_KEYWORDS = re.compile(
    r"\b(?:zaragoza|spain|espa[ñn]a|catalu[ñn]a|catalonia|madrid|barcelona|valencia|sevilla|bilbao|seur|correos|mrw)\b",
    re.IGNORECASE,
)

_US_REGION_KEYWORDS = re.compile(
    r"\b(?:los\s+angeles|los\s+[aá]ngeles|california|usa\b|u\.s\.a\.?|united\s+states|usps|ontrac|lasership|fedex)\b",
    re.IGNORECASE,
)

# Ephemeral / non-memorable patterns (FR-009)
_EPHEMERAL_NOISE_PATTERN = re.compile(
    r"(?:"
    r"^\s*(?:where\s+is\s+package|¿?d[oó]nde\s+est[aá]\s+el\s+paquete)\b"
    r"|^\s*(?:perfect(?:o)?\s*,?\s*(?:that\s+resolved\s+it|ya\s+qued[oó]\s+resuelto)|thanks|thank\s+you|gracias)\b"
    r"|^\s*(?:translate\s+this|trad[uú]ceme\s+esto)\b"
    r")",
    re.IGNORECASE,
)

# Operational candidate detection patterns (FR-004)
_CARRIER_RULE_CUE_PATTERN = re.compile(
    r"\b(?:no\s+longer\s+covers|ya\s+no\s+cubre|local\s+carriers?\s+must\s+be\s+used|hay\s+que\s+usar\s+el\s+carrier\s+local|"
    r"carrier\s+local|discontinued|coverage|cobertura|route\s+change|max\s+weight|peso\s+m[aá]ximo|"
    r"must\s+be\s+used\s+starting|stopped\s+operating|dej[oó]\s+de\s+operar)\b",
    re.IGNORECASE,
)

_INCIDENT_CONTEXT_CUE_PATTERN = re.compile(
    r"\b(?:delays?\s+reported|retrasos?\s+reportados?|retrasos?\s+en\s+la\s+ruta|"
    r"port\s+strike|huelga\s+portuaria|huelga\s+de\s+transportistas|transport\s+strike|"
    r"third\s+ticket|tres\s+tickets|recurring\s+incident|weather\s+disruption)\b",
    re.IGNORECASE,
)

_B2B_PREFERENCE_CUE_PATTERN = re.compile(
    r"\b(?:always\s+requests?|siempre\s+quiere|monthly\s+(?:performance\s+)?report|reporte\s+mensual|"
    r"returns?\s+breakdown|desglose\s+de\s+devoluciones|cosmetics\s+brand|cliente\s+de\s+cosm[eé]ticos|"
    r"b2b\s+client\s+always)\b",
    re.IGNORECASE,
)


def _infer_country_code(text: str, carrier: Optional[str] = None) -> Optional[str]:
    """Infer ISO 2-letter country code ('ES' or 'US') from text or carrier context."""
    if _ES_REGION_KEYWORDS.search(text):
        return "ES"
    if _US_REGION_KEYWORDS.search(text):
        return "US"
    if carrier:
        c_low = carrier.lower()
        if c_low in ("seur", "correos", "mrw", "gls"):
            return "ES"
        if c_low in ("usps", "ontrac", "lasership", "fedex", "ups"):
            return "US"
    return None


def _detect_carrier_name(text: str) -> Optional[str]:
    """Return canonical carrier name if mentioned in text."""
    lowered = text.lower()
    for token, canonical in _KNOWN_CARRIERS:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return canonical
    return None


def extract_memory_candidate(
    user_message: str,
    thread_id: Optional[str] = None,
    guardrail_validator: Optional[MemoryGuardrailPort] = None,
) -> Optional[MemoryProposal]:
    """Evaluate a user message in a single turn and extract a structured MemoryProposal if memorable (T012, FR-008, FR-009).

    Args:
        user_message: Raw or sanitized operator message.
        thread_id: Optional thread or session ID.
        guardrail_validator: Optional MemoryGuardrailPort (defaults to MemoryGuardrailValidator).

    Returns:
        MemoryProposal with status='pending' if a valid operational candidate is detected
        and passes all anti-poisoning guardrails; otherwise None.
    """
    if not user_message or len(user_message.strip()) < 10:
        return None

    cleaned = " ".join(user_message.strip().split())
    if _EPHEMERAL_NOISE_PATTERN.search(cleaned):
        return None

    validator = guardrail_validator or MemoryGuardrailValidator()

    # Pre-check raw input against anti-poisoning and sensitive data guardrails
    pre_verdict = validator.validate_candidate(
        content=cleaned,
        category="carrier_rule",
        target_entity="general",
    )
    if not pre_verdict.allowed:
        return None

    carrier_name = _detect_carrier_name(cleaned)
    has_carrier_cue = bool(_CARRIER_RULE_CUE_PATTERN.search(cleaned))
    has_incident_cue = bool(_INCIDENT_CONTEXT_CUE_PATTERN.search(cleaned))
    has_b2b_cue = bool(_B2B_PREFERENCE_CUE_PATTERN.search(cleaned))

    # Pure inquiries ending with '?' without operational correction cues are non-memorable
    if cleaned.endswith("?") and not (has_carrier_cue or has_incident_cue or has_b2b_cue):
        return None

    category: Optional[MemoryCategory] = None
    target_entity: Optional[str] = None
    country_code: Optional[str] = None

    if (carrier_name and has_carrier_cue) or (
        has_carrier_cue and not has_incident_cue and not has_b2b_cue
    ):
        category = "carrier_rule"
        target_entity = carrier_name or (
            "Zaragoza" if "zaragoza" in cleaned.lower() else "Regional Carrier"
        )
        country_code = _infer_country_code(cleaned, carrier=target_entity)
    elif has_incident_cue:
        category = "incident_context"
        if re.search(r"\blos\s+[aá]ngeles\b", cleaned, re.IGNORECASE):
            target_entity = "Los Angeles"
            country_code = "US"
        elif re.search(r"\bzaragoza\b", cleaned, re.IGNORECASE):
            target_entity = "Zaragoza"
            country_code = "ES"
        else:
            target_entity = carrier_name or "Regional Operations"
            country_code = _infer_country_code(cleaned, carrier=carrier_name)
    elif has_b2b_cue:
        category = "b2b_preference"
        if re.search(r"\b(?:cosmetics\s+brand|cliente\s+de\s+cosm[eé]ticos)\b", cleaned, re.IGNORECASE):
            target_entity = "Cosmetics Brand"
        else:
            target_entity = "B2B Client"
        country_code = _infer_country_code(cleaned)
    else:
        return None

    summary = mask_sensitive_pii(cleaned)[:300]
    final_verdict = validator.validate_candidate(
        content=summary,
        category=category,
        target_entity=target_entity,
    )
    if not final_verdict.allowed:
        return None

    now = datetime.now(timezone.utc)
    return MemoryProposal(
        proposal_id=str(uuid.uuid4()),
        category=category,
        target_entity=target_entity,
        country_code=country_code,
        summary=summary,
        status="pending",
        source_message=mask_sensitive_pii(cleaned)[:500],
        confidence=0.92,
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        thread_id=thread_id,
    )


class UserIntentClassifier(UserIntentClassifierPort):
    """Structured classifier evaluating follow-up user turns regarding active memory proposals (T019, FR-011)."""

    _EDIT_PATTERN = re.compile(
        r"^\s*(?:yes\s*,?\s*)?(?:please\s+)?(?:remember|save|store|keep|guarda|gu[aá]rdalo|recuerda|recu[eé]rdalo)"
        r"(?:\s+(?:it|that|this|eso|esa\s+regla))?\s*,?\s+"
        r"(?:but\s+|except\s+|pero\s+|excepto\s+|only\s+for\s+|solo\s+para\s+)(.+)$",
        re.IGNORECASE,
    )

    _APPROVE_PREFIX_PATTERN = re.compile(
        r"^\s*(?:"
        r"(?:yes|yeah|yep|s[ií]|claro|por\s+supuesto)\s*,?\s*(?:please\s+|por\s+favor\s+)?(?:remember|save|store|keep|confirm|approve|guarda|gu[aá]rdalo|recuerda|recu[eé]rdalo)(?:\s+(?:that|this|it|the))?(?:\s+rule)?(?:\s+for\s+[A-Za-z0-9_-]+)?(?:\s+to\s+memory|\s+en\s+memoria|\s+para\s+futuras\s+sesiones|\s+por\s+favor)?"
        r"|(?:confirmed|approved|approve)\s*,?\s*(?:and\s+)?(?:save|remember|store)\s+(?:that|this|it)(?:\s+rule)?(?:\s+to\s+memory)?"
        r"|(?:please\s+)?(?:save|remember)\s+(?:that|this)\s+rule(?:\s+for\s+[A-Za-z0-9_-]+)?"
        r")[\s.!]*",
        re.IGNORECASE,
    )

    _REJECT_PREFIX_PATTERN = re.compile(
        r"^\s*(?:"
        r"no\s*,?\s*(?:please\s+)?(?:do\s+not|don't|no\s+lo|no)\s+(?:save|remember|store|guardes|guardar|recuerdes)(?:\s+(?:that|this|it|eso|esa\s+regla))?(?:\s+rule)?(?:\s+in\s+memory|\s+en\s+memoria)?"
        r"|(?:reject|discard|cancel)\s+(?:that|this)?\s*(?:proposal|rule|it)?\s*,?\s*(?:do\s+not|don't)?\s*(?:store|save)?(?:\s+it)?"
        r"|(?:do\s+not|don't)\s+(?:save|remember|store)\s+(?:that|this|it)(?:\s+rule)?"
        r")[\s.!]*",
        re.IGNORECASE,
    )

    _RESIDUAL_CONNECTOR_PATTERN = re.compile(
        r"^\s*(?:,\s*)?(?:and\s+|also\s+|y\s+|adem[aá]s\s+)?(.+)$",
        re.IGNORECASE,
    )

    def classify(
        self,
        user_message: str,
        proposal_summary: str,
    ) -> UserIntentClassification:
        """Classify user follow-up message into approve, reject, edit, or unrelated_or_ambiguous."""
        if not user_message or not user_message.strip():
            return UserIntentClassification(
                intent="unrelated_or_ambiguous",
                confidence=0.95,
                refined_rule=None,
                residual_query=None,
            )

        cleaned = " ".join(user_message.strip().split())

        # 1. Check for conditional refinement / edit intent (e.g. "Remember it, but only for packages over 5kg")
        edit_match = self._EDIT_PATTERN.match(cleaned)
        if edit_match:
            refinement_raw = edit_match.group(1).strip().rstrip(".")
            # Guard against questions like "what about Seville?"
            if "?" not in refinement_raw and not re.match(
                r"^(?:what|where|how|can\s+you|check|qu[eé]|d[oó]nde)\b",
                refinement_raw,
                re.IGNORECASE,
            ):
                # Re-attach trigger preposition if matched in the connector group
                lower_cleaned = cleaned.lower()
                if "only for" in lower_cleaned and not refinement_raw.lower().startswith("only for"):
                    refinement_clause = f"only for {refinement_raw}"
                elif "except" in lower_cleaned and not refinement_raw.lower().startswith("except"):
                    refinement_clause = f"except {refinement_raw}"
                elif "solo para" in lower_cleaned and not refinement_raw.lower().startswith("solo para"):
                    refinement_clause = f"solo para {refinement_raw}"
                else:
                    refinement_clause = refinement_raw

                base_summary = (proposal_summary or "").strip().rstrip(".")
                refined_rule = (
                    f"{base_summary} ({refinement_clause})"
                    if base_summary
                    else refinement_clause
                )
                return UserIntentClassification(
                    intent="edit",
                    confidence=0.93,
                    refined_rule=refined_rule,
                    residual_query=None,
                )

        # 2. Check for explicit approval (with optional multi-intent residual query)
        approve_match = self._APPROVE_PREFIX_PATTERN.match(cleaned)
        if approve_match:
            remainder = cleaned[approve_match.end() :].strip()
            residual_query = self._extract_residual_query(remainder)
            return UserIntentClassification(
                intent="approve",
                confidence=0.95,
                refined_rule=None,
                residual_query=residual_query,
            )

        # 3. Check for explicit rejection (with optional multi-intent residual query)
        reject_match = self._REJECT_PREFIX_PATTERN.match(cleaned)
        if reject_match:
            remainder = cleaned[reject_match.end() :].strip()
            residual_query = self._extract_residual_query(remainder)
            return UserIntentClassification(
                intent="reject",
                confidence=0.95,
                refined_rule=None,
                residual_query=residual_query,
            )

        # 4. Safe Default: Any ambiguous reply ("ok", "maybe later", "Yes, but what about Seville?")
        # or topic shift ("Can you check current stock for SKU-401?") defaults to unrelated_or_ambiguous
        is_operational_question = len(cleaned) >= 12 and cleaned.lower() not in (
            "maybe later",
            "hmm not sure",
            "not sure",
            "i guess",
        )
        return UserIntentClassification(
            intent="unrelated_or_ambiguous",
            confidence=0.90,
            refined_rule=None,
            residual_query=cleaned if is_operational_question else None,
        )

    def _extract_residual_query(self, remainder: str) -> Optional[str]:
        """Extract a trailing operational inquiry from a multi-intent message (FR-015)."""
        if not remainder:
            return None
        match = self._RESIDUAL_CONNECTOR_PATTERN.match(remainder)
        if not match:
            return None
        candidate = match.group(1).strip()
        # Ignore short polite suffixes like "thanks" or "please"
        if len(candidate) < 6 or candidate.lower().rstrip(".!") in (
            "please",
            "thanks",
            "thank you",
            "por favor",
            "gracias",
            "for future sessions",
            "para futuras sesiones",
        ):
            return None
        return candidate


class AgentMemoryService:
    """Application service coordinating proposal lifecycle, intent resolution, recall, and consolidation."""

    def __init__(
        self,
        memory_repository: AgentMemoryRepositoryPort,
        audit_repository: MemoryAuditLogRepositoryPort,
        guardrail_validator: Optional[MemoryGuardrailPort] = None,
        intent_classifier: Optional[UserIntentClassifierPort] = None,
    ) -> None:
        """Initialize AgentMemoryService with isolated repositories and validators."""
        self._memory_repo = memory_repository
        self._audit_repo = audit_repository
        self._guardrail_validator = guardrail_validator or MemoryGuardrailValidator()
        self._intent_classifier = intent_classifier or UserIntentClassifier()
        self._lock = threading.RLock()
        # Single pending proposal queue per thread_id (FR-012)
        self._pending_by_thread: Dict[str, MemoryProposal] = {}
        self._proposals_by_id: Dict[str, MemoryProposal] = {}

    @property
    def memory_repository(self) -> AgentMemoryRepositoryPort:
        """Return the underlying AgentMemoryRepositoryPort."""
        return self._memory_repo

    @property
    def audit_repository(self) -> MemoryAuditLogRepositoryPort:
        """Return the underlying MemoryAuditLogRepositoryPort."""
        return self._audit_repo

    def get_pending_proposal(self, thread_id: Optional[str]) -> Optional[MemoryProposal]:
        """Return the active pending proposal for `thread_id`, or None if none is active."""
        if not thread_id:
            return None
        with self._lock:
            proposal = self._pending_by_thread.get(thread_id)
            if proposal and proposal.status == "pending":
                return proposal
            return None

    def get_proposal_by_id(self, proposal_id: str) -> Optional[MemoryProposal]:
        """Retrieve an in-flight or resolved proposal by its `proposal_id`."""
        with self._lock:
            return self._proposals_by_id.get(proposal_id)

    def evaluate_turn_for_proposal(
        self,
        user_message: str,
        base_answer: str,
        thread_id: Optional[str] = None,
        language: str = "en",
    ) -> Tuple[Optional[MemoryProposal], str]:
        """Perform single-call memory candidate evaluation and attach confirmation prompt if valid (FR-008, FR-010, FR-012).

        Enforces the single-pending-proposal queue limit (FR-012): if an unresolved proposal
        is already pending for `thread_id`, no secondary proposal is created.
        """
        effective_thread = thread_id or "default"
        with self._lock:
            existing_pending = self._pending_by_thread.get(effective_thread)
            if existing_pending is not None and existing_pending.status == "pending":
                # Suppress secondary proposal while one is active (FR-012)
                return existing_pending, base_answer

            proposal = extract_memory_candidate(
                user_message=user_message,
                thread_id=effective_thread,
                guardrail_validator=self._guardrail_validator,
            )
            if proposal is None:
                return None, base_answer

            self._pending_by_thread[effective_thread] = proposal
            self._proposals_by_id[proposal.proposal_id] = proposal

            self._audit_repo.record_entry(
                MemoryAuditLogEntry(
                    log_id=str(uuid.uuid4()),
                    proposal_id=proposal.proposal_id,
                    memory_id=None,
                    event_type="proposed",
                    classified_intent=None,
                    user_message=mask_sensitive_pii(user_message),
                    resulting_action="proposal_created",
                    session_id=effective_thread,
                    timestamp=datetime.now(timezone.utc),
                    details={
                        "category": proposal.category,
                        "target_entity": proposal.target_entity,
                        "country_code": proposal.country_code,
                        "summary": proposal.summary,
                    },
                )
            )

            prompt = (
                PROPOSAL_CONFIRMATION_PROMPT_ES
                if (language or "en").lower().startswith("es")
                else PROPOSAL_CONFIRMATION_PROMPT_EN
            )
            combined_answer = (
                f"{base_answer.strip()}\n\n{prompt}"
                if base_answer.strip()
                else prompt
            )
            return proposal, combined_answer

    def resolve_pending_proposal(
        self,
        thread_id: Optional[str],
        user_message: str,
        operator_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate user's subsequent message against an active pending proposal (FR-011, FR-013, FR-014, FR-015).

        Returns:
            Dictionary describing resolution (`status`, `classified_intent`, `resulting_action`,
            `committed_memory_id`, `updated_proposal`, `residual_query`, `acknowledgment_text`),
            or None if no pending proposal existed for `thread_id`.
        """
        if not thread_id:
            return None

        with self._lock:
            pending = self._pending_by_thread.get(thread_id)
            if pending is None or pending.status != "pending":
                return None

            classification = self._intent_classifier.classify(
                user_message=user_message,
                proposal_summary=pending.summary,
            )
            now = datetime.now(timezone.utc)
            sanitized_msg = mask_sensitive_pii(user_message)

            if classification.intent == "approve":
                expires_at = (
                    now + timedelta(days=DEFAULT_INCIDENT_TTL_DAYS)
                    if pending.category == "incident_context"
                    else None
                )
                record = PersistentMemoryRecord(
                    memory_id=str(uuid.uuid4()),
                    category=pending.category,
                    target_entity=pending.target_entity,
                    country_code=pending.country_code,
                    content=pending.summary,
                    source_proposal_id=pending.proposal_id,
                    operator_confirmed_by=operator_id or thread_id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    expires_at=expires_at,
                )
                saved = self._memory_repo.save_memory(record)
                approved_proposal = MemoryProposal(
                    proposal_id=pending.proposal_id,
                    category=pending.category,
                    target_entity=pending.target_entity,
                    country_code=pending.country_code,
                    summary=pending.summary,
                    status="approved",
                    source_message=pending.source_message,
                    confidence=pending.confidence,
                    created_at=pending.created_at,
                    expires_at=pending.expires_at,
                    thread_id=pending.thread_id,
                )
                self._proposals_by_id[pending.proposal_id] = approved_proposal
                del self._pending_by_thread[thread_id]

                self._audit_repo.record_entry(
                    MemoryAuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        proposal_id=pending.proposal_id,
                        memory_id=saved.memory_id,
                        event_type="approved",
                        classified_intent="approve",
                        user_message=sanitized_msg,
                        resulting_action="memory_persisted",
                        session_id=thread_id,
                        timestamp=now,
                        details={
                            "category": saved.category,
                            "target_entity": saved.target_entity,
                            "country_code": saved.country_code,
                        },
                    )
                )
                return {
                    "proposal_id": pending.proposal_id,
                    "status": "approved",
                    "classified_intent": "approve",
                    "resulting_action": "memory_persisted",
                    "committed_memory_id": saved.memory_id,
                    "updated_proposal": None,
                    "residual_query": classification.residual_query,
                    "acknowledgment_text": (
                        f"Confirmed. I have saved the operational memory rule for "
                        f"{saved.target_entity}: '{saved.content}'."
                    ),
                }

            if classification.intent == "edit":
                new_summary = (classification.refined_rule or pending.summary).strip()
                verdict = self._guardrail_validator.validate_candidate(
                    content=new_summary,
                    category=pending.category,
                    target_entity=pending.target_entity,
                )
                if not verdict.allowed:
                    del self._pending_by_thread[thread_id]
                    self._audit_repo.record_entry(
                        MemoryAuditLogEntry(
                            log_id=str(uuid.uuid4()),
                            proposal_id=pending.proposal_id,
                            memory_id=None,
                            event_type="discarded",
                            classified_intent="edit",
                            user_message=sanitized_msg,
                            resulting_action="proposal_discarded",
                            session_id=thread_id,
                            timestamp=now,
                            details={"violation_code": verdict.violation_code},
                        )
                    )
                    return {
                        "proposal_id": pending.proposal_id,
                        "status": "discarded",
                        "classified_intent": "edit",
                        "resulting_action": "proposal_discarded",
                        "committed_memory_id": None,
                        "updated_proposal": None,
                        "residual_query": None,
                        "acknowledgment_text": (
                            "The edited memory rule violated enterprise guardrails and was discarded."
                        ),
                    }

                edited_proposal = MemoryProposal(
                    proposal_id=pending.proposal_id,
                    category=pending.category,
                    target_entity=pending.target_entity,
                    country_code=pending.country_code,
                    summary=new_summary,
                    status="pending",
                    source_message=pending.source_message,
                    confidence=pending.confidence,
                    created_at=pending.created_at,
                    expires_at=now + timedelta(minutes=15),
                    thread_id=pending.thread_id,
                )
                self._pending_by_thread[thread_id] = edited_proposal
                self._proposals_by_id[pending.proposal_id] = edited_proposal

                self._audit_repo.record_entry(
                    MemoryAuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        proposal_id=pending.proposal_id,
                        memory_id=None,
                        event_type="edited",
                        classified_intent="edit",
                        user_message=sanitized_msg,
                        resulting_action="proposal_edited",
                        session_id=thread_id,
                        timestamp=now,
                        details={"updated_summary": new_summary},
                    )
                )
                return {
                    "proposal_id": pending.proposal_id,
                    "status": "edited",
                    "classified_intent": "edit",
                    "resulting_action": "proposal_edited",
                    "committed_memory_id": None,
                    "updated_proposal": edited_proposal,
                    "residual_query": classification.residual_query,
                    "acknowledgment_text": (
                        f"I have updated the proposed rule to: '{new_summary}'. "
                        f"{PROPOSAL_CONFIRMATION_PROMPT_EN}"
                    ),
                }

            if classification.intent == "reject":
                rejected_proposal = MemoryProposal(
                    proposal_id=pending.proposal_id,
                    category=pending.category,
                    target_entity=pending.target_entity,
                    country_code=pending.country_code,
                    summary=pending.summary,
                    status="rejected",
                    source_message=pending.source_message,
                    confidence=pending.confidence,
                    created_at=pending.created_at,
                    expires_at=pending.expires_at,
                    thread_id=pending.thread_id,
                )
                self._proposals_by_id[pending.proposal_id] = rejected_proposal
                del self._pending_by_thread[thread_id]

                self._audit_repo.record_entry(
                    MemoryAuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        proposal_id=pending.proposal_id,
                        memory_id=None,
                        event_type="rejected",
                        classified_intent="reject",
                        user_message=sanitized_msg,
                        resulting_action="proposal_discarded",
                        session_id=thread_id,
                        timestamp=now,
                        details={},
                    )
                )
                return {
                    "proposal_id": pending.proposal_id,
                    "status": "rejected",
                    "classified_intent": "reject",
                    "resulting_action": "proposal_discarded",
                    "committed_memory_id": None,
                    "updated_proposal": None,
                    "residual_query": classification.residual_query,
                    "acknowledgment_text": (
                        "Understood. I have discarded the memory proposal without saving."
                    ),
                }

            # Default safe discard for unrelated_or_ambiguous (FR-013)
            discarded_proposal = MemoryProposal(
                proposal_id=pending.proposal_id,
                category=pending.category,
                target_entity=pending.target_entity,
                country_code=pending.country_code,
                summary=pending.summary,
                status="discarded",
                source_message=pending.source_message,
                confidence=pending.confidence,
                created_at=pending.created_at,
                expires_at=pending.expires_at,
                thread_id=pending.thread_id,
            )
            self._proposals_by_id[pending.proposal_id] = discarded_proposal
            del self._pending_by_thread[thread_id]

            self._audit_repo.record_entry(
                MemoryAuditLogEntry(
                    log_id=str(uuid.uuid4()),
                    proposal_id=pending.proposal_id,
                    memory_id=None,
                    event_type="discarded",
                    classified_intent="unrelated_or_ambiguous",
                    user_message=sanitized_msg,
                    resulting_action="proposal_discarded",
                    session_id=thread_id,
                    timestamp=now,
                    details={"reason": "safe_default_discard_on_ambiguity_or_topic_shift"},
                )
            )
            return {
                "proposal_id": pending.proposal_id,
                "status": "discarded",
                "classified_intent": "unrelated_or_ambiguous",
                "resulting_action": "proposal_discarded",
                "committed_memory_id": None,
                "updated_proposal": None,
                "residual_query": classification.residual_query,
                "acknowledgment_text": (
                    "The pending memory proposal was safely discarded without saving."
                ),
            }

    def apply_explicit_feedback(
        self,
        proposal_id: str,
        action: Literal["approve", "reject", "edit"],
        refined_content: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply out-of-band REST feedback to a pending memory proposal (T024)."""
        with self._lock:
            proposal = self._proposals_by_id.get(proposal_id)
            if proposal is None or proposal.status not in ("pending", "edited"):
                raise MemoryNotFoundError(
                    entity_id=proposal_id,
                    entity_name="MemoryProposal",
                    message=f"Active memory proposal '{proposal_id}' was not found or already resolved.",
                )

            thread_id = proposal.thread_id or "default"
            now = datetime.now(timezone.utc)

            if action == "approve":
                expires_at = (
                    now + timedelta(days=DEFAULT_INCIDENT_TTL_DAYS)
                    if proposal.category == "incident_context"
                    else None
                )
                record = PersistentMemoryRecord(
                    memory_id=str(uuid.uuid4()),
                    category=proposal.category,
                    target_entity=proposal.target_entity,
                    country_code=proposal.country_code,
                    content=proposal.summary,
                    source_proposal_id=proposal.proposal_id,
                    operator_confirmed_by=operator_id or thread_id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    expires_at=expires_at,
                )
                saved = self._memory_repo.save_memory(record)
                updated = MemoryProposal(
                    proposal_id=proposal.proposal_id,
                    category=proposal.category,
                    target_entity=proposal.target_entity,
                    country_code=proposal.country_code,
                    summary=proposal.summary,
                    status="approved",
                    source_message=proposal.source_message,
                    confidence=proposal.confidence,
                    created_at=proposal.created_at,
                    expires_at=proposal.expires_at,
                    thread_id=proposal.thread_id,
                )
                self._proposals_by_id[proposal_id] = updated
                self._pending_by_thread.pop(thread_id, None)
                self._audit_repo.record_entry(
                    MemoryAuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        proposal_id=proposal_id,
                        memory_id=saved.memory_id,
                        event_type="approved",
                        classified_intent="approve",
                        user_message=f"[REST_FEEDBACK:approve] operator={operator_id or 'anonymous'}",
                        resulting_action="memory_persisted",
                        session_id=thread_id,
                        timestamp=now,
                        details={"operator_id": operator_id},
                    )
                )
                return {
                    "proposal_id": proposal_id,
                    "status": "approved",
                    "resulting_action": "memory_persisted",
                    "committed_memory_id": saved.memory_id,
                }

            if action == "edit":
                new_summary = (refined_content or proposal.summary).strip()
                verdict = self._guardrail_validator.validate_candidate(
                    content=new_summary,
                    category=proposal.category,
                    target_entity=proposal.target_entity,
                )
                if not verdict.allowed:
                    raise MemoryGuardrailViolationError(
                        violation_code=verdict.violation_code or "GUARDRAIL_VIOLATION",
                        reason=verdict.reason or "Edited content violated memory guardrails.",
                    )
                updated = MemoryProposal(
                    proposal_id=proposal.proposal_id,
                    category=proposal.category,
                    target_entity=proposal.target_entity,
                    country_code=proposal.country_code,
                    summary=new_summary,
                    status="pending",
                    source_message=proposal.source_message,
                    confidence=proposal.confidence,
                    created_at=proposal.created_at,
                    expires_at=now + timedelta(minutes=15),
                    thread_id=proposal.thread_id,
                )
                self._proposals_by_id[proposal_id] = updated
                self._pending_by_thread[thread_id] = updated
                self._audit_repo.record_entry(
                    MemoryAuditLogEntry(
                        log_id=str(uuid.uuid4()),
                        proposal_id=proposal_id,
                        memory_id=None,
                        event_type="edited",
                        classified_intent="edit",
                        user_message=mask_sensitive_pii(new_summary),
                        resulting_action="proposal_edited",
                        session_id=thread_id,
                        timestamp=now,
                        details={"operator_id": operator_id},
                    )
                )
                return {
                    "proposal_id": proposal_id,
                    "status": "edited",
                    "resulting_action": "proposal_edited",
                    "committed_memory_id": None,
                }

            # Reject
            updated = MemoryProposal(
                proposal_id=proposal.proposal_id,
                category=proposal.category,
                target_entity=proposal.target_entity,
                country_code=proposal.country_code,
                summary=proposal.summary,
                status="rejected",
                source_message=proposal.source_message,
                confidence=proposal.confidence,
                created_at=proposal.created_at,
                expires_at=proposal.expires_at,
                thread_id=proposal.thread_id,
            )
            self._proposals_by_id[proposal_id] = updated
            self._pending_by_thread.pop(thread_id, None)
            self._audit_repo.record_entry(
                MemoryAuditLogEntry(
                    log_id=str(uuid.uuid4()),
                    proposal_id=proposal_id,
                    memory_id=None,
                    event_type="rejected",
                    classified_intent="reject",
                    user_message=f"[REST_FEEDBACK:reject] operator={operator_id or 'anonymous'}",
                    resulting_action="proposal_discarded",
                    session_id=thread_id,
                    timestamp=now,
                    details={"operator_id": operator_id},
                )
            )
            return {
                "proposal_id": proposal_id,
                "status": "rejected",
                "resulting_action": "proposal_discarded",
                "committed_memory_id": None,
            }

    def recall_relevant_memories(self, query: str) -> List[str]:
        """Recall active operational memories relevant to `query` without touching Qdrant (T027, FR-006, FR-007)."""
        if not query or len(query.strip()) < 3:
            return []

        now = datetime.now(timezone.utc)
        self._memory_repo.evict_expired(now)

        all_active = self._memory_repo.search_memories(active_only=True)
        if not all_active:
            return []

        lowered_query = query.lower()
        query_country = _infer_country_code(query)
        query_carrier = _detect_carrier_name(query)

        wants_carrier = bool(
            query_carrier
            or re.search(
                r"\b(?:carriers?|shipments?|shipping|deliver(?:y|ies)|assign|route|rural|zaragoza|transportista|env[ií]os?)\b",
                lowered_query,
            )
        )
        wants_incident = bool(
            re.search(
                r"\b(?:delays?|delayed|incidents?|strikes?|port|los\s+angeles|zaragoza|retrasos?|huelga)\b",
                lowered_query,
            )
        )
        wants_b2b = bool(
            re.search(
                r"\b(?:reports?|monthly|cosmetics|b2b|brand|preferences?|reportes?|cosm[eé]ticos)\b",
                lowered_query,
            )
        )

        recalled: List[str] = []
        seen: set[str] = set()

        for rec in all_active:
            match = False
            rec_target_low = rec.target_entity.lower()

            if rec_target_low in lowered_query:
                match = True
            elif (
                query_country
                and rec.country_code
                and rec.country_code.upper() == query_country
            ):
                if rec.category == "carrier_rule" and wants_carrier:
                    match = True
                elif rec.category == "incident_context" and wants_incident:
                    match = True
            elif rec.category == "carrier_rule" and wants_carrier and not query_country:
                match = True
            elif rec.category == "incident_context" and wants_incident and not query_country:
                match = True
            elif rec.category == "b2b_preference" and wants_b2b:
                match = True

            if match:
                formatted = (
                    f"[{rec.category}:{rec.target_entity}"
                    f"{'/' + rec.country_code if rec.country_code else ''}] {rec.content}"
                )
                if formatted not in seen:
                    seen.add(formatted)
                    recalled.append(formatted)

        return recalled

    def get_consolidated_carrier_profile(
        self, carrier: str, country_code: str = "ES"
    ) -> Optional[ConsolidatedCarrierProfile]:
        """Retrieve the consolidated operational profile for `(carrier, country_code)` (T035)."""
        return self._memory_repo.get_consolidated_carrier_profile(
            carrier=carrier,
            country_code=country_code,
        )

    def evict_expired_memories(
        self, cutoff_time: Optional[datetime] = None
    ) -> int:
        """Evict expired transient memories and record audit log entries (T036)."""
        effective_cutoff = cutoff_time or datetime.now(timezone.utc)
        evicted_count = self._memory_repo.evict_expired(effective_cutoff)
        if evicted_count > 0:
            self._audit_repo.record_entry(
                MemoryAuditLogEntry(
                    log_id=str(uuid.uuid4()),
                    proposal_id=None,
                    memory_id=None,
                    event_type="evicted",
                    classified_intent=None,
                    user_message="[TTL_EVICTION_ROUTINE]",
                    resulting_action="memory_evicted",
                    session_id=None,
                    timestamp=effective_cutoff,
                    details={"evicted_count": evicted_count},
                )
            )
        return evicted_count

    def list_audit_logs(
        self,
        proposal_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryAuditLogEntry]:
        """Return immutable audit log entries ordered newest first."""
        return self._audit_repo.list_entries(
            proposal_id=proposal_id,
            event_type=event_type,
            limit=limit,
        )


__all__ = [
    "AgentMemoryService",
    "DEFAULT_INCIDENT_TTL_DAYS",
    "PROPOSAL_CONFIRMATION_PROMPT_EN",
    "PROPOSAL_CONFIRMATION_PROMPT_ES",
    "UserIntentClassifier",
    "extract_memory_candidate",
]
