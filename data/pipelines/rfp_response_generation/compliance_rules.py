"""Deterministic compliance rules engine enforcing TrackFlow briefing §5 rules.

Evaluates the 5 mandatory commercial compliance rules:
1. RULE-CURRENCY: Price quoted in USD for US (client_country == 'US') or EUR for Spain ('ES').
2. RULE-SLA: On-time delivery SLA (%) committed in proposal.
3. RULE-RETURNS-TIME: No returns processing promised under 48 hours.
4. RULE-DISCOUNT-TIERS: Volume discount table or tier breakdown included.
5. RULE-CARRIER-RATES: Negotiated carrier rates never revealed (only final client prices).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Dict, List, Literal, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from domain.rfp.entities import ComplianceEvaluation  # noqa: E402


RuleId = Literal[
    "RULE-CURRENCY",
    "RULE-SLA",
    "RULE-RETURNS-TIME",
    "RULE-DISCOUNT-TIERS",
    "RULE-CARRIER-RATES",
]


@dataclass(frozen=True)
class ComplianceRuleDefinition:
    """Standardized business compliance rule enforced by the evaluator."""

    rule_id: RuleId
    description: str
    severity: Literal["CRITICAL"]
    failure_message: str


BRIEFING_COMPLIANCE_RULES: Dict[RuleId, ComplianceRuleDefinition] = {
    "RULE-CURRENCY": ComplianceRuleDefinition(
        rule_id="RULE-CURRENCY",
        description="Price quoted in USD for US client or EUR for Spain (client_country).",
        severity="CRITICAL",
        failure_message=(
            "Violates RULE-CURRENCY: All prices must be quoted exclusively in the currency "
            "matching client_country (USD for US, EUR for ES) without mixing currencies."
        ),
    ),
    "RULE-SLA": ComplianceRuleDefinition(
        rule_id="RULE-SLA",
        description="On-time delivery SLA (canonical 90%) committed in proposal.",
        severity="CRITICAL",
        failure_message=(
            "Violates RULE-SLA: Proposal must explicitly state the committed canonical 90% on-time "
            "delivery / operational SLA percentage per contractual standards (trackflow-sla-delivery)."
        ),
    ),
    "RULE-RETURNS-TIME": ComplianceRuleDefinition(
        rule_id="RULE-RETURNS-TIME",
        description="No returns processing promised under 48 hours.",
        severity="CRITICAL",
        failure_message=(
            "Violates RULE-RETURNS-TIME: TrackFlow policy strictly prohibits promising "
            "returns processing or inspection turnaround in less than 48 hours."
        ),
    ),
    "RULE-DISCOUNT-TIERS": ComplianceRuleDefinition(
        rule_id="RULE-DISCOUNT-TIERS",
        description="Volume discount table included with Miguel Torres commercial governance.",
        severity="CRITICAL",
        failure_message=(
            "Violates RULE-DISCOUNT-TIERS: Proposal must include a volume discount table "
            "or tiered volume discount breakdown explicitly conditioned on commercial approval "
            "by Miguel Torres (Director Comercial)."
        ),
    ),
    "RULE-CARRIER-RATES": ComplianceRuleDefinition(
        rule_id="RULE-CARRIER-RATES",
        description="Negotiated carrier rates never revealed (only final client prices).",
        severity="CRITICAL",
        failure_message=(
            "Violates RULE-CARRIER-RATES: Proposal must never disclose TrackFlow's confidential "
            "negotiated internal carrier base rates or carrier wholesale margins; quote only "
            "final client-facing prices."
        ),
    ),
}


def validate_rule_currency(draft_text: str, client_country: str) -> Tuple[bool, str]:
    """Verify RULE-CURRENCY: USD for US, EUR for ES, and no wrong currency quoted."""
    text = draft_text or ""
    country = (client_country or "ES").upper()

    has_usd = bool(
        re.search(r"\bUSD\b", text, re.IGNORECASE)
        or re.search(r"\$\s*\d", text)
        or re.search(r"\d\s*\$", text)
        or re.search(r"\bdólares\b|\bdollars?\b", text, re.IGNORECASE)
    )
    has_eur = bool(
        re.search(r"\bEUR\b", text, re.IGNORECASE)
        or re.search(r"€\s*\d", text)
        or re.search(r"\d\s*€", text)
        or re.search(r"\beuros?\b", text, re.IGNORECASE)
    )

    if country == "US":
        if not has_usd:
            return (
                False,
                "Violates RULE-CURRENCY: Client country is US, but draft does not quote prices in USD ($).",
            )
        if has_eur:
            return (
                False,
                "Violates RULE-CURRENCY: Client country is US (requires USD), but draft contains EUR (€) pricing.",
            )
    else:  # ES
        if not has_eur:
            return (
                False,
                "Violates RULE-CURRENCY: Client country is ES, but draft does not quote prices in EUR (€).",
            )
        if has_usd:
            return (
                False,
                "Violates RULE-CURRENCY: Client country is ES (requires EUR), but draft contains USD ($) pricing.",
            )

    return True, ""


def validate_rule_sla(draft_text: str) -> Tuple[bool, str]:
    """Verify RULE-SLA: Contractual canonical 90% on-time delivery / operational SLA committed in proposal."""
    text = draft_text or ""
    # Look for SLA mention alongside a canonical 90% percentage commitment
    has_sla_keyword = bool(
        re.search(
            r"\bsla\b|entrega a tiempo|on[-\s]?time|cumplimiento|nivel de servicio",
            text,
            re.IGNORECASE,
        )
    )
    has_canonical_90 = bool(re.search(r"\b90(?:[.,]0+)?\s*%", text))

    if not (has_sla_keyword and has_canonical_90):
        return (
            False,
            BRIEFING_COMPLIANCE_RULES["RULE-SLA"].failure_message,
        )
    return True, ""


def validate_rule_returns_time(draft_text: str) -> Tuple[bool, str]:
    """Verify RULE-RETURNS-TIME: No returns processing promised under 48 hours."""
    text = draft_text or ""
    lower = text.lower()

    # Check for explicit sub-48h return turnaround promises
    # e.g., "24 hours", "24h", "24 horas", "12 hours", "same-day return", "mismo día", "under 48 hours", "< 48h", "24-48"
    sub_48_patterns = [
        r"(?:return|returns|devoluci[oó]n|devoluciones|reacondicionamiento|inspecci[oó]n|reverse|turnaround)[^\n.;]{0,80}?\b(?:12|24|36)\s*(?:-\s*48\s*)?(?:h|hr|hrs|hours?|horas?)\b",
        r"\b(?:12|24|36)\s*(?:-\s*48\s*)?(?:h|hr|hrs|hours?|horas?)\b[^\n.;]{0,80}?(?:return|returns|devoluci[oó]n|devoluciones|reacondicionamiento|inspecci[oó]n|reverse|turnaround)",
        r"(?:same[-\s]?day|mismo\s+d[ií]a|inmediat[oa]|instant[aá]ne[oa])[^\n.;]{0,60}?(?:return|returns|devoluci[oó]n|devoluciones|inspecci[oó]n|turnaround)",
        r"(?:return|returns|devoluci[oó]n|devoluciones|inspecci[oó]n|turnaround)[^\n.;]{0,60}?(?:same[-\s]?day|mismo\s+d[ií]a|inmediat[oa]|instant[aá]ne[oa])",
        r"(?:menos\s+de|under|below|within|inferior\s+a|<)\s*(?:12|24|36|47)\s*(?:h|hr|hrs|hours?|horas?)",
    ]

    for pattern in sub_48_patterns:
        match = re.search(pattern, lower)
        if match:
            snippet = match.group(0)
            # Allow explicit negation such as "no prometemos devoluciones en 24 horas" or "never under 48 hours"
            if any(
                neg in snippet
                for neg in [
                    "no ",
                    "nunca",
                    "jamás",
                    "prohib",
                    "never",
                    "not ",
                    "cannot",
                    "mínimo 48",
                    "minimum 48",
                ]
            ):
                continue
            return (
                False,
                f"{BRIEFING_COMPLIANCE_RULES['RULE-RETURNS-TIME'].failure_message} (Detected: '{snippet.strip()}')",
            )

    # Also detect numeric hours < 48 directly tied to return turnaround
    hour_matches = re.finditer(
        r"(?:turnaround|procesamiento de devoluciones|return processing|inspección de devoluciones)[^\n.;]{0,40}?\b(\d{1,2})\s*(?:h|hr|hrs|hours?|horas?)\b",
        lower,
    )
    for m in hour_matches:
        hours_val = int(m.group(1))
        if hours_val < 48:
            return (
                False,
                f"{BRIEFING_COMPLIANCE_RULES['RULE-RETURNS-TIME'].failure_message} (Promised {hours_val}h < 48h minimum).",
            )

    return True, ""


def validate_rule_discount_tiers(draft_text: str) -> Tuple[bool, str]:
    """Verify RULE-DISCOUNT-TIERS: Volume discount table included with Miguel Torres governance."""
    text = draft_text or ""
    lower = text.lower()

    has_discount_term = any(
        term in lower
        for term in [
            "descuento por volumen",
            "descuentos por volumen",
            "tabla de descuentos",
            "volume discount",
            "discount tier",
            "discount table",
            "tramos de descuento",
            "escalado de descuentos",
        ]
    )
    # Check for markdown table pipes or multiple percentage tier rows
    has_table_or_tiers = ("|" in text and "%" in text) or (
        len(re.findall(r"\b\d{1,2}\s*%", text)) >= 2
        and any(t in lower for t in ["tier", "tramo", "volumen", "volume", "pedidos", "orders", "pallets", "m³", "m3"])
    )
    has_governance = "miguel torres" in lower

    if not (has_discount_term and has_table_or_tiers and has_governance):
        return (
            False,
            BRIEFING_COMPLIANCE_RULES["RULE-DISCOUNT-TIERS"].failure_message,
        )
    return True, ""


def validate_rule_carrier_rates(draft_text: str) -> Tuple[bool, str]:
    """Verify RULE-CARRIER-RATES: Negotiated internal carrier rates are never revealed."""
    text = draft_text or ""
    lower = text.lower()

    forbidden_patterns = [
        r"tarifa\s+negociada\s+(?:con|de)\s+(?:fedex|ups|dhl|usps|seur|mrw|correos|gls)",
        r"negotiated\s+carrier\s+(?:rate|cost|tariff)",
        r"internal\s+carrier\s+(?:cost|rate|tariff|margin)",
        r"costo\s+interno\s+(?:de\s+transportista|negociado)",
        r"tarifa\s+mayorista\s+de\s+transportista",
        r"wholesale\s+carrier\s+rate",
        r"(?:fedex|ups|dhl|usps|seur|mrw|correos|gls)\s+(?:internal\s+cost|negotiated\s+rate|tarifa\s+interna|costo\s+base)\s*[:=]\s*[\$€]?\s*\d",
        r"nuestro\s+costo\s+con\s+(?:fedex|ups|dhl|usps|seur|mrw|correos|gls)\s+es",
        r"our\s+negotiated\s+cost\s+with\s+(?:fedex|ups|dhl|usps|seur|mrw|correos|gls)\s+is",
    ]

    for pattern in forbidden_patterns:
        match = re.search(pattern, lower)
        if match:
            snippet = match.group(0)
            # Exclude compliance disclaimer statements that say we do NOT reveal negotiated carrier rates
            context_start = max(0, match.start() - 40)
            context_window = lower[context_start : match.end() + 20]
            if any(
                neg in context_window
                for neg in [
                    "no revel",
                    "nunca revel",
                    "sin revel",
                    "never reveal",
                    "do not disclose",
                    "not reveal",
                    "without revealing",
                    "without disclosure",
                    "confidential",
                ]
            ):
                continue
            return (
                False,
                f"{BRIEFING_COMPLIANCE_RULES['RULE-CARRIER-RATES'].failure_message} (Detected: '{snippet.strip()}')",
            )

    return True, ""


def evaluate_compliance_rules(
    draft_text: str,
    client_country: str,
    department_id: str = "warehouse",
) -> ComplianceEvaluation:
    """Evaluate all 5 mandatory briefing §5 compliance rules against a section draft.

    Args:
        draft_text: Markdown content of the generated department section.
        client_country: 'US' or 'ES' determining expected currency.
        department_id: Department identifier ('warehouse', 'lastmile', 'reverse').

    Returns:
        ComplianceEvaluation value object with pass_status, violated rule_ids, and violations.
    """
    _ = department_id  # Rules apply across all proposal sections per briefing §5
    violated_rule_ids: List[str] = []
    violation_messages: List[str] = []

    checks: List[Tuple[RuleId, Tuple[bool, str]]] = [
        ("RULE-CURRENCY", validate_rule_currency(draft_text, client_country)),
        ("RULE-SLA", validate_rule_sla(draft_text)),
        ("RULE-RETURNS-TIME", validate_rule_returns_time(draft_text)),
        ("RULE-DISCOUNT-TIERS", validate_rule_discount_tiers(draft_text)),
        ("RULE-CARRIER-RATES", validate_rule_carrier_rates(draft_text)),
    ]

    for rule_id, (passed, message) in checks:
        if not passed:
            violated_rule_ids.append(rule_id)
            violation_messages.append(message)

    return ComplianceEvaluation(
        pass_status=len(violated_rule_ids) == 0,
        rule_ids=violated_rule_ids,
        violations=violation_messages,
    )
