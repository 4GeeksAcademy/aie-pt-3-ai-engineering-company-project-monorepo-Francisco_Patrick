"""Memory Anti-Poisoning Defenses & Sensitive Data Filtering Guardrails (T033).

Implements `MemoryGuardrailValidator` adhering to `MemoryGuardrailPort`,
enforcing TrackFlow enterprise memory boundaries (`trackflow-BRIEFING.es.md`,
FR-003, FR-005, FR-017, SC-004):
1. `SENSITIVE_LOCATION`: Blocks exact physical delivery addresses of B2C end consumers
   and exact physical premises/street/floor/suite locations of B2B clients.
2. `WAREHOUSE_PHYSICAL_SECURITY`: Blocks internal warehouse floor layouts, aisle/shelf paths,
   and physical security routes/checkpoints.
3. `ONE_OFF_COMPLAINT`: Blocks isolated, single-package customer complaints without a
   repeatable operational pattern.
4. `CONTRACT_NEGOTIATION`: Blocks active commercial contracts in negotiation and sales CRM data.
5. `POLICY_OVERRIDE`: Blocks global policy override injections disguised as operational notes.
"""

import re
from domain.agent.entities import MemoryGuardrailVerdict
from domain.agent.ports import MemoryGuardrailPort

_EMAIL_PII_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# 1. Sensitive physical location patterns (both B2C and B2B street/number/floor/door/suite addresses)
_SENSITIVE_LOCATION_PATTERN = re.compile(
    r"(?:"
    r"\b(?:calle|avenida|avda\.?|paseo|plaza|street|st\.?|avenue|ave\.?|terrace|boulevard|blvd\.?|road|rd\.?)\s+[A-Za-zÁÉÍÓÚáéíóúÑñ0-9\s]{2,35}\s+\d+\b"
    r"|\b(?:piso|puerta|planta|oficina|apt\.?|apartment|suite|ste\.?)\s*[0-9A-Za-z]+\b"
    r"|\b(?:lives\s+at|vive\s+en|direcci[oó]n\s+exacta|exact\s+delivery\s+(?:dock\s+)?address|destinatario\s+final\s+b2c\s+vive)\b"
    r")",
    re.IGNORECASE,
)

# 2. Internal warehouse layout & physical security routes
_WAREHOUSE_SECURITY_PATTERN = re.compile(
    r"(?:"
    r"\b(?:aisle|shelf|hallway|pasillo|estanter[ií]a)\s*[0-9A-Za-z]+\b"
    r"|\b(?:security\s+(?:checkpoint|door|gate|route)|puerta\s+de\s+seguridad|control\s+de\s+seguridad)\b"
    r"|\b(?:internal\s+warehouse\s+(?:floor\s+)?(?:route|layout|path)|ruta\s+interna\s+(?:del\s+almac[eé]n|pasa\s+por))\b"
    r")",
    re.IGNORECASE,
)

# 3. Active commercial contract negotiations & CRM pipeline
_CONTRACT_NEGOTIATION_PATTERN = re.compile(
    r"(?:"
    r"\b(?:negotiat(?:ing|ion)|en\s+negociaci[oó]n)\b"
    r"|\b(?:commercial\s+contract|contrato\s+comercial)\b"
    r"|\b(?:sales\s+crm|\bcrm\b|cl[aá]usulas?\s+de\s+confidencialidad|\bnda\b)\b"
    r")",
    re.IGNORECASE,
)

# 4. Global policy override poisoning attempts
_POLICY_OVERRIDE_PATTERN = re.compile(
    r"(?:"
    r"\b(?:override\s+company|ignore\s+all\s+sla|waived\s+forever|without\s+vp\s+approval)\b"
    r"|\b(?:return\s+window\s+is\s+365\s+days|all\s+return\s+fees\s+are\s+waived)\b"
    r")",
    re.IGNORECASE,
)

# 5. One-off single package complaint indicators
_SINGLE_PACKAGE_PATTERN = re.compile(
    r"(?:"
    r"\b(?:package|tracking|paquete|shipment)\s+(?:con\s+tracking\s+)?[A-Z]{2,5}-?\d{3,8}\b"
    r"|\b(?:single\s+shipment|one\s+customer|isolated\s+complaint|incidencia\s+puntual|un\s+solo\s+paquete)\b"
    r"|\b(?:arrived\s+(?:torn|crushed|damaged)|lleg[oó]\s+con\s+la\s+caja\s+golpeada)\b"
    r")",
    re.IGNORECASE,
)

_RECURRING_PATTERN_INDICATOR = re.compile(
    r"\b(?:third\s+ticket|tres\s+tickets|multiple\s+tickets|this\s+week|esta\s+semana|"
    r"always|siempre|no\s+longer\s+covers|ya\s+no\s+cubre|recurring|recurrente)\b",
    re.IGNORECASE,
)


def mask_sensitive_pii(text: str) -> str:
    """Mask email addresses and PII tokens in user messages prior to audit logging (Principle IV)."""
    if not text:
        return ""
    return _EMAIL_PII_PATTERN.sub("[REDACTED_EMAIL]", text)


class MemoryGuardrailValidator(MemoryGuardrailPort):
    """Validates candidate memories against TrackFlow anti-poisoning and sensitive data rules."""

    def validate_candidate(
        self,
        content: str,
        category: str,
        target_entity: str,
    ) -> MemoryGuardrailVerdict:
        """Evaluate candidate content against forbidden categories.

        Args:
            content: Candidate memory summary or user message text.
            category: Proposed memory category.
            target_entity: Target entity identifier.

        Returns:
            MemoryGuardrailVerdict indicating whether the candidate is allowed.
        """
        text = f"{content or ''} {target_entity or ''}".strip()
        if not text:
            return MemoryGuardrailVerdict(
                allowed=False,
                violation_code="EMPTY_CANDIDATE",
                reason="Candidate memory content cannot be empty.",
            )

        if _WAREHOUSE_SECURITY_PATTERN.search(text):
            return MemoryGuardrailVerdict(
                allowed=False,
                violation_code="WAREHOUSE_PHYSICAL_SECURITY",
                reason="Internal warehouse floor layouts, aisle paths, and security routes cannot be stored in agent memory.",
            )

        if _SENSITIVE_LOCATION_PATTERN.search(text):
            return MemoryGuardrailVerdict(
                allowed=False,
                violation_code="SENSITIVE_LOCATION",
                reason="Exact B2C or B2B physical delivery addresses and premises locations are forbidden under physical security guardrails.",
            )

        if _CONTRACT_NEGOTIATION_PATTERN.search(text):
            return MemoryGuardrailVerdict(
                allowed=False,
                violation_code="CONTRACT_NEGOTIATION",
                reason="Active commercial contract negotiations and sales CRM data are excluded from support agent memory.",
            )

        if _POLICY_OVERRIDE_PATTERN.search(text):
            return MemoryGuardrailVerdict(
                allowed=False,
                violation_code="POLICY_OVERRIDE",
                reason="Unauthorized global corporate policy overrides cannot be injected into operational memory.",
            )

        if _SINGLE_PACKAGE_PATTERN.search(text) and not _RECURRING_PATTERN_INDICATOR.search(text):
            return MemoryGuardrailVerdict(
                allowed=False,
                violation_code="ONE_OFF_COMPLAINT",
                reason="Isolated single-package complaints or tracking lookups without a repeatable operational pattern are not memorable.",
            )

        return MemoryGuardrailVerdict(
            allowed=True,
            violation_code=None,
            reason=None,
        )


__all__ = ["MemoryGuardrailValidator", "mask_sensitive_pii"]
