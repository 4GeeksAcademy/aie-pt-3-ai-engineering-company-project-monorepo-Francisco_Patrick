# Domain Port Contracts: Agent Harnessing & Guardrails (Part 2 of 2)

**Feature**: `030-agent-guardrails` (`feature/agent-guardrails`)  
**Location**: `services/api/domain/agent/ports.py`  
**Date**: 2026-11-21  

Adheres strictly to Hexagonal Architecture and Monorepo Constitution Principle I (Service Boundaries & Domain Isolation), Principle II (Public API Compatibility & Strict Contract Serialization), and Principle IV (Defensive Error Handling & Zero Sensitive Data Leaks).

---

## 1. InputGuardrailPort

Evaluates untrusted user inputs prior to tool planning or memory resolution, enforcing immutable system authority (anti-jailbreak), personal task refusal, and casual small talk / general logistics trivia classification with mandatory redirection (FR-003, FR-004, FR-005, FR-006).

```python
from abc import ABC, abstractmethod
from domain.agent.entities import GuardrailEvaluationResult


class InputGuardrailPort(ABC):
    """Pre-execution input guardrail port enforcing system authority and domain scope."""

    @abstractmethod
    def evaluate_input(
        self,
        query: str,
        language: str = "en",
    ) -> GuardrailEvaluationResult:
        """Evaluate user query against security (jailbreak) and content (scope) guardrails.

        Precedence:
        1. Security (`jailbreak_attempt`): Direct instruction override, roleplay/persona adoption,
           hypothetical debug/developer mode, system prompt extraction, or bilingual override.
           -> action='block', failure_category='security'.
        2. Prohibited Personal Task (`personal_task`): Essays, homework, coding, therapy,
           or unrelated general-purpose assistant tasks.
           -> action='block', failure_category='content'.
        3. Permitted Out-of-Domain Casual / General Logistics Trivia (`casual_trivia`):
           Brief small talk or non-TrackFlow logistics definitions (e.g., '¿Qué es la logística inversa?').
           -> action='redirect', failure_category='content'.
        4. In-Domain (`in_domain`): Shipment tracking, return policies/SLAs, delivery incidents.
           -> action='allow', failure_category='none'.

        Args:
            query: Raw or sanitized user inquiry.
            language: Target language ISO code ('en' or 'es').

        Returns:
            GuardrailEvaluationResult detailing action, failure_category, reason_code, and refusal/redirect message.
        """
```

---

## 2. AuthorizationGuardrailPort

Enforces session-scoped order ownership (`FR-007`) and country-specific policy integrity (`FR-008`, `US` vs. `ES`).

```python
from abc import ABC, abstractmethod
from typing import Optional
from domain.agent.entities import (
    AuthenticatedSessionContext,
    GuardrailEvaluationResult,
)


class AuthorizationGuardrailPort(ABC):
    """Guardrail port enforcing session-scoped order authorization and US/Spain policy separation."""

    @abstractmethod
    def evaluate_authorization_and_policy(
        self,
        query: str,
        session_context: Optional[AuthenticatedSessionContext] = None,
        language: str = "en",
    ) -> GuardrailEvaluationResult:
        """Verify order ownership against `session_context` and prevent cross-country policy mixing.

        Rules:
        1. If the query references a specific customer order or tracking number (e.g., '#45821')
           and `session_context` is None or the order ID is not in `session_context.authorized_order_ids`,
           returns action='block', failure_category='security', input_category='unauthorized_order'.
        2. Resolves authoritative country ('US' or 'ES') from:
           (a) `session_context.order_country_map` for a referenced order,
           (b) explicit order fulfillment location in the request (e.g., Los Angeles -> 'US', Zaragoza/Madrid -> 'ES'),
           (c) `session_context.primary_operating_country`.
        3. If the user asks to apply Spain's return policy/SLA to a US order (or US policy to a Spain order),
           returns action='block', failure_category='content', input_category='policy_mismatch',
           enforcing the authoritative country's policy.

        Args:
            query: User inquiry string.
            session_context: Optional AuthenticatedSessionContext for the active turn.
            language: Response language preference ('en' or 'es').

        Returns:
            GuardrailEvaluationResult with action, failure_category, resolved_country, and refusal message if blocked.
        """
```

---

## 3. ContextSanitizerPort

Enforces the two-tier defense on external RAG knowledge chunks and operational tool outputs (FR-009).

```python
from abc import ABC, abstractmethod
from typing import List, Tuple
from domain.agent.entities import (
    GuardrailEvaluationResult,
    InventoryToolOutput,
    RetrievedContext,
    TicketToolOutput,
)


class ContextSanitizerPort(ABC):
    """Two-tier external content sanitizer isolating RAG chunks and tool payloads from system authority."""

    @abstractmethod
    def sanitize_text_chunk(
        self,
        text: str,
        source_label: str,
    ) -> GuardrailEvaluationResult:
        """Apply two-tier defense to an external text snippet.

        - Tier 1 (Primary): Strip/neutralize embedded imperative directives while wrapping
          remaining safe factual content in passive `<external_context>` delimiters
          (`action='redirect'`, `failure_category='security'`, `input_category='external_injection'`).
        - Tier 2 (Quarantine): If the payload is purely adversarial or severely corrupted
          with no safe factual content remaining, quarantine/drop the snippet
          (`action='block'`, `failure_category='security'`, `input_category='external_injection'`).
        - Clean: Wrap in passive `<external_context>` delimiters (`action='allow'`, `failure_category='none'`).

        Args:
            text: Raw text from RAG chunk or external tool payload.
            source_label: Provenance identifier (e.g. 'rag:returns-policy', 'tool:ticket_tool').

        Returns:
            GuardrailEvaluationResult with sanitized_text and classification details.
        """

    @abstractmethod
    def sanitize_rag_contexts(
        self,
        contexts: List[RetrievedContext],
    ) -> Tuple[List[RetrievedContext], List[GuardrailEvaluationResult]]:
        """Sanitize a list of RetrievedContext chunks, dropping quarantined Tier-2 chunks."""

    @abstractmethod
    def sanitize_ticket_output(
        self,
        output: TicketToolOutput,
    ) -> Tuple[TicketToolOutput, List[GuardrailEvaluationResult]]:
        """Sanitize descriptions/titles inside TicketToolOutput records."""

    @abstractmethod
    def sanitize_inventory_output(
        self,
        output: InventoryToolOutput,
    ) -> Tuple[InventoryToolOutput, List[GuardrailEvaluationResult]]:
        """Sanitize descriptions/names inside InventoryToolOutput records."""
```

---

## 4. OutputGuardrailPort

Validates all generated responses before returning them to the user, enforcing structural validity, system instruction confidentiality, restricted corporate/customer data blocking (`trackflow-BRIEFING.es.md`), and mandatory casual-trivia redirection (FR-010).

```python
from abc import ABC, abstractmethod
from typing import Optional
from domain.agent.entities import (
    AuthenticatedSessionContext,
    GuardrailEvaluationResult,
)


class OutputGuardrailPort(ABC):
    """Post-generation output guardrail port validating structure, security, and restricted domain content."""

    @abstractmethod
    def validate_output(
        self,
        query: str,
        candidate_answer: str,
        session_context: Optional[AuthenticatedSessionContext] = None,
        casual_redirect_required: bool = False,
        language: str = "en",
    ) -> GuardrailEvaluationResult:
        """Inspect and enforce guardrails on a candidate response before delivery.

        Checks:
        1. `structural`: Non-empty string, no raw unparsed JSON wrapper leakage, no raw stack traces
           or unclosed internal XML authority tags (`<system_instructions>`).
        2. `security` (System Prompt Leakage): Blocks any response leaking internal system prompt instructions
           or immutable boundary declarations.
        3. `content` / `security` (Restricted TrackFlow Data per `trackflow-BRIEFING.es.md`):
           - Cross-customer order/tracking data not owned by `session_context`.
           - Negotiated carrier rates (UPS, FedEx, DHL, MRW, SEUR) or confidential B2B contract terms.
           - Exact physical warehouse locations or internal floor/security routes (aisles, shelves, gates).
        4. `content` (Mandatory Redirection): When `casual_redirect_required=True`, ensures the response
           concludes with an explicit redirection back to TrackFlow's shipment tracking, returns, and incidents scope.

        Args:
            query: User inquiry string.
            candidate_answer: Candidate response generated by the workflow.
            session_context: Optional AuthenticatedSessionContext for verifying order disclosures.
            casual_redirect_required: Whether the turn was classified as casual small talk / general trivia.
            language: Target response language ('en' or 'es').

        Returns:
            GuardrailEvaluationResult with final safe `sanitized_text`, `action`, and `failure_category`.
        """
```

---

## 5. GuardrailObservabilityPort

Records structured `GuardrailAuditEvent` entries with redacted previews and produces `GuardrailSummaryReport` views (FR-011, FR-012).

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.agent.entities import (
    GuardrailAuditEvent,
    GuardrailEvaluationResult,
    GuardrailSummaryReport,
)


class GuardrailObservabilityPort(ABC):
    """Port interface for logging guardrail interventions and querying aggregated trigger summaries."""

    @abstractmethod
    def record_evaluation(
        self,
        result: GuardrailEvaluationResult,
        session_id: str,
        raw_preview: str,
        trace_id: Optional[str] = None,
    ) -> Optional[GuardrailAuditEvent]:
        """Record a guardrail evaluation outcome.

        Increments total evaluations count. When `result.action in ('block', 'redirect')`
        and `result.failure_category != 'none'`, creates a `GuardrailAuditEvent` with a
        sanitized/redacted preview snippet and appends it to the audit store.

        Args:
            result: GuardrailEvaluationResult from any guardrail layer.
            session_id: Active session or thread identifier.
            raw_preview: Raw input, chunk, or candidate output text to be redacted before storage.
            trace_id: Optional execution trace UUID.

        Returns:
            Created GuardrailAuditEvent if an intervention occurred, otherwise None.
        """

    @abstractmethod
    def get_summary(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> GuardrailSummaryReport:
        """Aggregate trigger counts by failure type ('structural', 'content', 'security') and layer.

        Args:
            session_id: Optional session filter.
            limit: Maximum number of recent audit events to include.

        Returns:
            GuardrailSummaryReport instance.
        """

    @abstractmethod
    def list_events(
        self,
        session_id: Optional[str] = None,
        failure_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[GuardrailAuditEvent]:
        """List recorded GuardrailAuditEvent entries ordered newest first."""

    @abstractmethod
    def clear(self) -> None:
        """Reset counters and stored events (used for deterministic test isolation)."""
```
