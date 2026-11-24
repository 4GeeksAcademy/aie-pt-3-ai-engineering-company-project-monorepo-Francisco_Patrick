"""Deterministic Conflict Arbitration Node & Briefing Rules Engine (Part 3 of 3).

Evaluates and resolves cross-department contradictions strictly via structured state conditions
and TrackFlow briefing rules (`docs/agentic-workflows/trackflow-BRIEFING.es.md` §7) without
stochastic LLM voting or unconstrained agent debate:

1. `volume-vs-capacity`:
   - Condition: Warehouse committed capacity < Last Mile assumed monthly volume.
   - Arbiter: Miguel Torres (Commercial Director).
   - Resolution: Cap proposal volume at warehouse capacity; require Last Mile downward adjustment.

2. `returns-sla-breach`:
   - Condition: Any department draft promises return turnaround < 48 hours.
   - Arbiter: Sofía Ramos (Reverse Logistics Lead) for `reverse`; Miguel Torres for other sections.
   - Resolution: Force `changes_requested` (`request_changes`) on offending section; block final synthesis.

3. `currency-mismatch`:
   - Condition: Section currencies conflict or contradict `client_country` (US -> USD, ES -> EUR).
   - Arbiter: Miguel Torres (Commercial Director).
   - Resolution: Rewrite offending sections into canonical country currency; if unresolved at iteration cap, mark rejected.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID, uuid4

from data.pipelines.rfp_approval_completion.state import (
    COMMERCIAL_DIRECTOR,
    REVERSE_LOGISTICS_LEAD,
    traced_node,
)
from domain.rfp.entities import ArbiterLiteral, ArbitrationLog

DEFAULT_MAX_REVISIONS = 2

_SUB_48H_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\b(?:12|24|36)\s*(?:-\s*hour|hours|hrs|h|horas)\b", re.IGNORECASE),
    re.compile(r"\bsame[-\s]day\s+return", re.IGNORECASE),
    re.compile(r"\b(?:under|less\s+than|menos\s+de|<)\s*48\s*(?:hours|hrs|h|horas)\b", re.IGNORECASE),
    re.compile(r"\bdevoluciones\s+en\s+24\s*horas\b", re.IGNORECASE),
]

_NEGATION_PREFIXES: Tuple[str, ...] = (
    "never ",
    "not ",
    "no ",
    "cannot ",
    "do not ",
    "don't ",
    "nunca ",
    "jamás ",
    "without ",
)


def resolve_canonical_currency(client_country: str) -> Literal["USD", "EUR"]:
    """Return canonical operating currency for client_country (US -> USD, ES -> EUR)."""
    country = (client_country or "ES").strip().upper()
    return "USD" if country == "US" else "EUR"


def _extract_warehouse_capacity(
    rfp_metadata: Dict[str, Any],
    warehouse_section: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Extract committed warehouse monthly capacity from section key_aspects, metadata, or draft text."""
    if warehouse_section:
        ka = warehouse_section.get("key_aspects") or {}
        for key in (
            "warehouse_capacity",
            "max_monthly_capacity",
            "committed_capacity",
            "monthly_capacity",
            "capacity",
        ):
            val = ka.get(key)
            if isinstance(val, (int, float)) and int(val) > 0:
                return int(val)
            if isinstance(val, str) and val.replace(",", "").strip().isdigit():
                return int(val.replace(",", "").strip())

        draft = str(warehouse_section.get("draft_content") or "")
        match = re.search(
            r"(?:max(?:imum)?\s+capacity|warehouse\s+capacity|committed\s+capacity|capacidad\s+m[aá]xima)[:\s]+([\d,]+)\s*(?:orders|pedidos|shipments|unidades)",
            draft,
            re.IGNORECASE,
        )
        if match:
            return int(match.group(1).replace(",", ""))

    meta_cap = rfp_metadata.get("warehouse_capacity") or rfp_metadata.get("max_warehouse_capacity")
    if isinstance(meta_cap, (int, float)) and int(meta_cap) > 0:
        return int(meta_cap)
    return None


def _extract_lastmile_volume(
    rfp_metadata: Dict[str, Any],
    lastmile_section: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Extract Last Mile assumed monthly order volume from section key_aspects, draft text, or metadata."""
    if lastmile_section:
        ka = lastmile_section.get("key_aspects") or {}
        for key in (
            "monthly_volume",
            "assumed_monthly_volume",
            "lastmile_volume",
            "order_volume",
        ):
            val = ka.get(key)
            if isinstance(val, (int, float)) and int(val) > 0:
                return int(val)
            if isinstance(val, str) and val.replace(",", "").strip().isdigit():
                return int(val.replace(",", "").strip())

        draft = str(lastmile_section.get("draft_content") or "")
        match = re.search(
            r"\b([\d,]+)\s+(?:monthly\s+(?:shipments|orders|parcels)|orders\s+per\s+month|shipments\s+per\s+month|pedidos\s+mensuales)\b",
            draft,
            re.IGNORECASE,
        )
        if match:
            parsed = int(match.group(1).replace(",", ""))
            if parsed > 0:
                return parsed

    meta_vol = rfp_metadata.get("monthly_volume")
    if isinstance(meta_vol, (int, float)) and int(meta_vol) > 0:
        return int(meta_vol)
    return None


def _has_returns_sla_breach(section: Dict[str, Any]) -> bool:
    """Detect whether a department section promises return turnaround under 48 hours."""
    ka = section.get("key_aspects") or {}
    for key in ("return_turnaround_hours", "turnaround_hours", "sla_turnaround_hours"):
        val = ka.get(key)
        if isinstance(val, (int, float)) and float(val) < 48:
            return True

    draft = str(section.get("draft_content") or "")
    if not draft:
        return False

    for line in draft.splitlines():
        lower_line = line.strip().lower()
        if not lower_line:
            continue
        # Only inspect lines discussing returns, turnaround, reverse, inspection, or devoluciones
        if not any(
            kw in lower_line
            for kw in ("return", "turnaround", "reverse", "devoluci", "reembolso", "inspection", "restock")
        ):
            continue
        # Skip explicitly negated statements such as "We never promise returns under 48 hours."
        if any(neg in lower_line for neg in _NEGATION_PREFIXES):
            continue
        for pattern in _SUB_48H_PATTERNS:
            if pattern.search(lower_line):
                return True
    return False


def _detect_section_currency_conflict(
    section: Dict[str, Any],
    canonical_currency: Literal["USD", "EUR"],
) -> bool:
    """Detect whether a section quotes a currency conflicting with canonical_currency."""
    ka = section.get("key_aspects") or {}
    sec_curr = ka.get("currency") or section.get("currency")
    if isinstance(sec_curr, str) and sec_curr.strip().upper() in ("USD", "EUR"):
        if sec_curr.strip().upper() != canonical_currency:
            return True

    draft = str(section.get("draft_content") or "")
    if not draft:
        return False

    forbidden_code = "EUR" if canonical_currency == "USD" else "USD"
    forbidden_symbol = "€" if canonical_currency == "USD" else "$"

    if re.search(rf"\b{forbidden_code}\b", draft):
        return True
    if forbidden_symbol in draft:
        return True
    return False


def _rewrite_draft_currency(
    draft_content: str,
    canonical_currency: Literal["USD", "EUR"],
) -> str:
    """Deterministically rewrite currency tokens and symbols to canonical_currency."""
    if not draft_content:
        return draft_content

    if canonical_currency == "EUR":
        rewritten = re.sub(r"\bUSD\b", "EUR", draft_content)
        rewritten = re.sub(r"\$(\d[\d,]*(?:\.\d+)?)", r"\1 EUR", rewritten)
        rewritten = rewritten.replace("$", "€")
        # Clean up duplicate "EUR EUR" if "$18.00 USD" became "18.00 EUR EUR"
        rewritten = re.sub(r"\bEUR\s+EUR\b", "EUR", rewritten)
    else:
        rewritten = re.sub(r"\bEUR\b", "USD", draft_content)
        rewritten = re.sub(r"€\s*(\d[\d,]*(?:\.\d+)?)", r"$\1 USD", rewritten)
        rewritten = rewritten.replace("€", "$")
        rewritten = re.sub(r"\bUSD\s+USD\b", "USD", rewritten)
    return rewritten


def evaluate_and_arbitrate_conflicts(
    ticket_id: UUID,
    rfp_metadata: Dict[str, Any],
    department_sections: Dict[str, Dict[str, Any]],
    max_revisions: int = 2,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], List[ArbitrationLog]]:
    """Run deterministic conflict detection and resolution across all active department sections.

    Returns:
        Tuple of (updated_rfp_metadata, updated_department_sections, generated_arbitration_logs).
    """
    updated_meta = copy.deepcopy(rfp_metadata or {})
    updated_sections = copy.deepcopy(department_sections or {})
    logs: List[ArbitrationLog] = []
    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Trigger 1: volume-vs-capacity (Miguel Torres)
    # -------------------------------------------------------------------------
    wh_sec = updated_sections.get("warehouse")
    lm_sec = updated_sections.get("lastmile")
    wh_capacity = _extract_warehouse_capacity(updated_meta, wh_sec)
    lm_volume = _extract_lastmile_volume(updated_meta, lm_sec)

    if (
        wh_capacity is not None
        and lm_volume is not None
        and wh_capacity < lm_volume
    ):
        updated_meta["monthly_volume"] = wh_capacity
        affected_depts: List[str] = []
        if "warehouse" in updated_sections:
            affected_depts.append("warehouse")
        if "lastmile" in updated_sections:
            affected_depts.append("lastmile")
            lm_entry = updated_sections["lastmile"]
            lm_ka = dict(lm_entry.get("key_aspects") or {})
            lm_ka["monthly_volume"] = wh_capacity
            lm_ka["capped_by_arbitration"] = True
            lm_entry["key_aspects"] = lm_ka

            old_draft = str(lm_entry.get("draft_content") or "")
            for raw_vol_str in (f"{lm_volume:,}", str(lm_volume)):
                if raw_vol_str in old_draft:
                    old_draft = old_draft.replace(raw_vol_str, str(wh_capacity))
            arbitration_banner = (
                f"\n\n> **[Arbitration - {COMMERCIAL_DIRECTOR}]**: Monthly shipment volume capped at "
                f"{wh_capacity} orders/month to align with Warehouse Operations capacity "
                f"(adjusted downward from {lm_volume} orders/month)."
            )
            if arbitration_banner not in old_draft:
                old_draft = old_draft + arbitration_banner
            lm_entry["draft_content"] = old_draft

            curr_iter = int(lm_entry.get("iteration_count", lm_entry.get("iteration", 0)) or 0)
            if curr_iter >= max_revisions:
                lm_entry["approval_status"] = "needs_human_review"
                lm_entry["escalation_note"] = (
                    f"Escalated to {COMMERCIAL_DIRECTOR}: volume-vs-capacity conflict reached max revision cap ({max_revisions})."
                )
            else:
                lm_entry["approval_status"] = "changes_requested"
                lm_entry["iteration_count"] = curr_iter + 1
                lm_entry["iteration"] = curr_iter + 1
            lm_entry["review_feedback"] = (
                f"Arbitration ({COMMERCIAL_DIRECTOR}): Warehouse max capacity is {wh_capacity} orders/month "
                f"vs Last Mile {lm_volume} orders/month. Proposal volume capped at {wh_capacity}; "
                "adjust Last Mile volume and pricing downward."
            )

        if not affected_depts:
            affected_depts = ["warehouse", "lastmile"]

        logs.append(
            ArbitrationLog(
                id=uuid4(),
                ticket_id=ticket_id,
                trigger_id="volume-vs-capacity",
                arbiter=COMMERCIAL_DIRECTOR,
                rule_applied=(
                    "Briefing §7 Rule 1 (Volume vs Capacity): Proposal volume cannot exceed Warehouse "
                    "committed capacity. Volume is capped at warehouse capacity and Last Mile must adjust "
                    "volume and pricing downward."
                ),
                resolution_details={
                    "affected_departments": affected_depts,
                    "action_taken": (
                        f"Capped proposal monthly volume to {wh_capacity} orders/month (from {lm_volume}) "
                        "and routed Last Mile for downward volume and pricing adjustment."
                    ),
                    "capped_volume": wh_capacity,
                    "previous_volume": lm_volume,
                    "enforced_currency": None,
                },
                created_at=now,
            )
        )

    # -------------------------------------------------------------------------
    # Trigger 2: returns-sla-breach (Sofía Ramos / Miguel Torres)
    # -------------------------------------------------------------------------
    sla_offending_depts: List[str] = []
    for dept_id, sec in updated_sections.items():
        if _has_returns_sla_breach(sec):
            sla_offending_depts.append(dept_id)
            curr_iter = int(sec.get("iteration_count", sec.get("iteration", 0)) or 0)
            sec_arbiter: ArbiterLiteral = (
                REVERSE_LOGISTICS_LEAD if dept_id == "reverse" else COMMERCIAL_DIRECTOR
            )
            if curr_iter >= max_revisions:
                sec["approval_status"] = "needs_human_review"
                sec["escalation_note"] = (
                    f"Escalated to {COMMERCIAL_DIRECTOR}: returns-sla-breach unresolved after {max_revisions} revisions."
                )
            else:
                sec["approval_status"] = "changes_requested"
                sec["iteration_count"] = curr_iter + 1
                sec["iteration"] = curr_iter + 1
            sec["review_feedback"] = (
                f"Arbitration ({sec_arbiter}): Returns turnaround < 48 hours violates TrackFlow Briefing Rule 5. "
                "Section must specify a minimum 48 to 72 hours return processing turnaround."
            )

    if sla_offending_depts:
        primary_arbiter: ArbiterLiteral = (
            REVERSE_LOGISTICS_LEAD
            if sla_offending_depts == ["reverse"]
            else COMMERCIAL_DIRECTOR
        )
        logs.append(
            ArbitrationLog(
                id=uuid4(),
                ticket_id=ticket_id,
                trigger_id="returns-sla-breach",
                arbiter=primary_arbiter,
                rule_applied=(
                    "Briefing §5 & §7 Rule 2 (Returns SLA Breach): TrackFlow never promises returns "
                    "processing turnaround under 48 hours. Offending sections are forced to request_changes "
                    "and block final document synthesis."
                ),
                resolution_details={
                    "affected_departments": sla_offending_depts,
                    "action_taken": (
                        f"Forced request_changes on {', '.join(sla_offending_depts)} for < 48h returns SLA promise "
                        "and blocked final document synthesis until compliant."
                    ),
                    "capped_volume": None,
                    "enforced_currency": None,
                },
                created_at=now,
            )
        )

    # -------------------------------------------------------------------------
    # Trigger 3: currency-mismatch (Miguel Torres)
    # -------------------------------------------------------------------------
    client_country = str(updated_meta.get("client_country") or "ES").upper()
    canonical_currency = resolve_canonical_currency(client_country)
    meta_currency = str(updated_meta.get("currency") or canonical_currency).upper()

    currency_offending_depts: List[str] = []
    for dept_id, sec in updated_sections.items():
        if _detect_section_currency_conflict(sec, canonical_currency):
            currency_offending_depts.append(dept_id)
            sec["draft_content"] = _rewrite_draft_currency(
                str(sec.get("draft_content") or ""),
                canonical_currency,
            )
            ka = dict(sec.get("key_aspects") or {})
            if "currency" in ka:
                ka["currency"] = canonical_currency
            sec["key_aspects"] = ka
            sec["currency"] = canonical_currency

            curr_iter = int(sec.get("iteration_count", sec.get("iteration", 0)) or 0)
            if curr_iter >= max_revisions and _detect_section_currency_conflict(sec, canonical_currency):
                sec["approval_status"] = "rejected"
                sec["review_feedback"] = (
                    f"Arbitration ({COMMERCIAL_DIRECTOR}): Section rejected due to unresolved currency mismatch after max revisions."
                )

    if meta_currency != canonical_currency or currency_offending_depts:
        updated_meta["currency"] = canonical_currency
        affected_curr_depts = (
            currency_offending_depts
            if currency_offending_depts
            else list(updated_sections.keys()) or ["warehouse"]
        )
        logs.append(
            ArbitrationLog(
                id=uuid4(),
                ticket_id=ticket_id,
                trigger_id="currency-mismatch",
                arbiter=COMMERCIAL_DIRECTOR,
                rule_applied=(
                    f"Briefing §5 & §7 Rule 3 (Currency Mismatch): Client country '{client_country}' "
                    f"mandates '{canonical_currency}'. All proposal sections are rewritten to canonical currency."
                ),
                resolution_details={
                    "affected_departments": affected_curr_depts,
                    "action_taken": (
                        f"Enforced canonical currency '{canonical_currency}' for country '{client_country}' "
                        f"across {', '.join(affected_curr_depts)}."
                    ),
                    "capped_volume": None,
                    "enforced_currency": canonical_currency,
                },
                created_at=now,
            )
        )

    return updated_meta, updated_sections, logs


@traced_node("arbitration_node")
def arbitration_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph deterministic arbitration node evaluating cross-department state conditions."""
    raw_tid = state.get("ticket_id")
    tid = UUID(str(raw_tid)) if raw_tid else uuid4()
    meta = dict(state.get("rfp_metadata") or {})
    sections = dict(state.get("department_sections") or {})
    max_revisions = int(state.get("max_revisions", 2))

    updated_meta, updated_sections, new_logs = evaluate_and_arbitrate_conflicts(
        ticket_id=tid,
        rfp_metadata=meta,
        department_sections=sections,
        max_revisions=max_revisions,
    )

    existing_logs = list(state.get("arbitration_logs") or [])
    for log_entry in new_logs:
        existing_logs.append(log_entry.to_schema_dict())

    return {
        "rfp_metadata": updated_meta,
        "department_sections": updated_sections,
        "arbitration_logs": existing_logs,
    }
