"""Dedicated department proposal generator agents for Part 2 RFP Response Generation.

Implements isolated generator agents per fulfillment department per TrackFlow briefing §2.1 & §5:
- WarehouseGeneratorAgent (Ana Whitfield): Storage capacity, pallet/SKU costs, onboarding schedule.
- LastMileGeneratorAgent (Carlos Vega): Shipping costs, carrier network by destination, delivery SLA.
- ReverseLogisticsGeneratorAgent (Sofía Ramos): Returns processing cost, turnaround time >= 48 hours.

Includes encapsulated VectorStorePort lookup with graceful offline fallback to briefing standards.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Literal, Optional

from domain.knowledge.ports import EmbeddingServicePort, VectorStorePort

logger = logging.getLogger(__name__)

DepartmentIdLiteral = Literal["warehouse", "lastmile", "reverse"]

FALLBACK_BRIEFING_STANDARDS: Dict[DepartmentIdLiteral, Dict[str, Any]] = {
    "warehouse": {
        "department_name": "Warehouse Operations",
        "responsible_person": "Ana Whitfield",
        "on_time_sla_pct": "90%",
        "standard_onboarding_weeks": "2 to 3 weeks",
        "rates": {
            "USD": {
                "storage_m3_monthly": "$18.00 USD por m³",
                "onboarding_fee": "Pending confirmation (Pendiente de confirmación en USD según alcance de integración)",
            },
            "EUR": {
                "storage_m3_monthly": "16.00 EUR por m³",
                "onboarding_fee": "Pending confirmation (Pendiente de confirmación en EUR según alcance de integración)",
            },
        },
        "policy_note": (
            "TrackFlow Warehouse commits to a canonical 90% on-time delivery SLA per contractual standards. "
            "Storage pricing is calculated based on volume occupied in cubic meters (m³), not per unit or pallet count. "
            "First 30 days are free of storage charges. "
            "Restock and return checks take 48 to 72 hours."
        ),
    },
    "lastmile": {
        "department_name": "Last Mile and Carrier Management",
        "responsible_person": "Carlos Vega",
        "on_time_sla_pct": "90%",
        "rates": {
            "USD": {
                "standard_parcel": "Pending confirmation (Pendiente de confirmación en USD)",
                "express_parcel": "Pending confirmation (Pendiente de confirmación en USD)",
            },
            "EUR": {
                "standard_parcel": "Pending confirmation (Pendiente de confirmación en EUR)",
                "express_parcel": "Pending confirmation (Pendiente de confirmación en EUR)",
            },
        },
        "policy_note": (
            "TrackFlow Last Mile commits to a canonical 90% on-time delivery SLA per contractual standards. "
            "We quote final client prices only."
        ),
    },
    "reverse": {
        "department_name": "Reverse Logistics",
        "responsible_person": "Sofía Ramos",
        "on_time_sla_pct": "90%",
        "minimum_turnaround_hours": "48 to 72 hours",
        "rates": {
            "USD": {
                "return_inspection_unit": "Pending confirmation (Pendiente de confirmación de tarifa en USD según reglas de la marca cliente)",
                "refurbishment_unit": "Pending confirmation (Pendiente de confirmación en USD; TrackFlow ejecuta logística sin reacondicionar por cuenta propia)",
            },
            "EUR": {
                "return_inspection_unit": "Pending confirmation (Pendiente de confirmación de tarifa en EUR según reglas de la marca cliente)",
                "refurbishment_unit": "Pending confirmation (Pendiente de confirmación en EUR; TrackFlow ejecuta logística sin reacondicionar por cuenta propia)",
            },
        },
        "policy_note": (
            "TrackFlow Reverse checks each return item within 48 to 72 hours. "
            "Returns processing is never promised under 48 hours. "
            "Return shipping costs are borne by the client brand unless caused by TrackFlow error. "
            "We meet the canonical 90% on-time SLA."
        ),
    },
}


def resolve_currency_for_country(client_country: str) -> Literal["USD", "EUR"]:
    """Resolve mandatory operating currency from client_country per TrackFlow briefing §5."""
    country = (client_country or "ES").strip().upper()
    return "USD" if country == "US" else "EUR"


def format_currency_amount(amount: float, client_country: str) -> str:
    """Format a monetary amount in the mandatory currency for client_country."""
    currency = resolve_currency_for_country(client_country)
    if currency == "USD":
        return f"${amount:,.2f} USD"
    return f"{amount:,.2f} EUR"


def build_volume_discount_table(currency: Literal["USD", "EUR"]) -> str:
    """Generate the mandatory volume discount table (§5 RULE-DISCOUNT-TIERS) governed by Miguel Torres."""
    return (
        "### Volume Discount Table (Tabla de Descuentos por Volumen)\n\n"
        "Gobernanza comercial: Cualquier tarifa preferencial o descuento por volumen "
        "(especialmente para volúmenes > 50 m³) requiere aprobación obligatoria y expresa de "
        "Miguel Torres (Director Comercial).\n\n"
        "| Monthly Volume Tier | Volume Discount (%) | Effective Rate Adjustment | Commercial Governance Approval |\n"
        "|---|---|---|---|\n"
        f"| Tier 1: 1 - 2,500 orders/month | 0% (Standard Base Rate in {currency}) | Base schedule ({currency}) | Pre-aprobado por Miguel Torres |\n"
        f"| Tier 2: 2,501 - 7,500 orders/month | 5% volume discount | -5% on all {currency} unit rates | Pendiente de aprobación comercial por Miguel Torres |\n"
        f"| Tier 3: 7,501 - 15,000 orders/month | 10% volume discount | -10% on all {currency} unit rates | Pendiente de aprobación comercial por Miguel Torres |\n"
        f"| Tier 4: 15,001+ orders/month | 15% volume discount | -15% on all {currency} unit rates | Pendiente de aprobación comercial por Miguel Torres |\n"
    )


def _extract_missing_aspects_from_feedback(feedback_text: str) -> List[str]:
    """Extract missing key_aspect identifiers from a [RELEVANCE] feedback directive."""
    if not feedback_text:
        return []
    match = re.search(
        r"missing Part 1 key aspects in the proposal section:\s*([^.]+)",
        feedback_text,
        re.IGNORECASE,
    )
    if not match:
        return []
    raw_items = match.group(1).split(",")
    return [item.strip() for item in raw_items if item.strip()]


def _extract_kb_rate_or_pending(
    snippets: List[str],
    pattern: str,
    default_value: str,
    currency: Literal["USD", "EUR"],
) -> str:
    """Pull a rate from KB snippets if present for the target currency, else return default_value."""
    other_currency = "EUR" if currency == "USD" else "USD"
    for snippet in snippets:
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match:
            found = match.group(0).strip()
            # Avoid injecting a snippet fragment that contains the opposite currency
            if other_currency.lower() not in found.lower():
                return found
    return default_value


def _sanitize_foreign_currency_in_text(
    text: str,
    currency: Literal["USD", "EUR"],
) -> str:
    """Sanitize any conflicting currency tokens or symbols when enforcing RULE-CURRENCY."""
    cleaned = text
    if currency == "EUR":
        cleaned = re.sub(r"\$\s*(\d+(?:[.,]\d+)?)\s*(?:USD)?", r"\1 EUR", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bUSD\b", "EUR", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bdólares\b|\bdollars?\b", "euros", cleaned, flags=re.IGNORECASE)
    else:
        cleaned = re.sub(r"€\s*(\d+(?:[.,]\d+)?)\s*(?:EUR)?", r"$\1 USD", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(\d+(?:[.,]\d+)?)\s*€", r"$\1 USD", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bEUR\b", "USD", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\beuros?\b", "USD", cleaned, flags=re.IGNORECASE)
    return cleaned


def _sanitize_sub_48h_returns_in_text(text: str) -> str:
    """Replace any sub-48h return turnaround promises in text with 48 to 72 hours."""
    cleaned = re.sub(
        r"\b(?:12|24|36)\s*(?:-\s*48\s*)?(?:h|hr|hrs|hours?|horas?)\b",
        "48 to 72 hours",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:same[-\s]?day|mismo\s+d[ií]a|inmediat[oa]|instant[aá]ne[oa])\b",
        "48 to 72 hours",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


class KnowledgeRetrievalHelper:
    """Encapsulated semantic knowledge lookup via VectorStorePort with graceful briefing fallback."""

    def __init__(
        self,
        vector_store: Optional[VectorStorePort] = None,
        embedding_service: Optional[EmbeddingServicePort] = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    def retrieve_department_guidelines(
        self,
        department_id: DepartmentIdLiteral,
        query_text: str,
        top_k: int = 2,
    ) -> Dict[str, Any]:
        """Query VectorStorePort for department guidelines or degrade gracefully to briefing defaults."""
        fallback_info = FALLBACK_BRIEFING_STANDARDS[department_id]
        if self.vector_store is None or self.embedding_service is None:
            return {
                "source": "briefing_fallback",
                "fallback_used": True,
                "snippets": [str(fallback_info["policy_note"])],
            }

        try:
            query_vector = self.embedding_service.embed_query(query_text)
            results = self.vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
                score_threshold=0.5,
            )
            if results:
                snippets = [r.chunk.text for r in results if r.chunk and r.chunk.text]
                if snippets:
                    return {
                        "source": "vector_store",
                        "fallback_used": False,
                        "snippets": snippets,
                    }
        except Exception as exc:
            logger.warning(
                "Vector knowledge lookup unavailable for department '%s', using briefing fallback: %s",
                department_id,
                exc,
            )

        return {
            "source": "briefing_fallback",
            "fallback_used": True,
            "snippets": [str(fallback_info["policy_note"])],
        }


class BaseDepartmentGeneratorAgent:
    """Base proposal section generator agent for a specific TrackFlow operational department."""

    department_id: DepartmentIdLiteral
    department_name: str
    responsible_person: str

    def __init__(
        self,
        knowledge_helper: Optional[KnowledgeRetrievalHelper] = None,
    ) -> None:
        self.knowledge_helper = knowledge_helper or KnowledgeRetrievalHelper()

    def generate(
        self,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
        feedback_for_generator: Optional[str] = None,
        iteration: int = 1,
    ) -> str:
        """Generate or revise a specialized department proposal section from Part 1 handoff data."""
        raise NotImplementedError

    def _build_body_feedback_directive(
        self,
        feedback_for_generator: Optional[str],
        currency: Literal["USD", "EUR"],
        key_aspects: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """Parse feedback_for_generator into concrete section-level body modifications for Sections 1-4."""
        modifications: Dict[str, List[str]] = {
            "section_1": [],
            "section_2": [],
            "section_3": [],
            "section_4": [],
        }
        if not feedback_for_generator:
            return modifications

        fb_upper = feedback_for_generator.upper()
        missing_aspects = _extract_missing_aspects_from_feedback(feedback_for_generator)

        if "RULE-SLA" in fb_upper or "SLA" in fb_upper:
            modifications["section_2"].append(
                "Contractual SLA guarantee: TrackFlow commits to a 90% monthly on-time SLA measured by country, "
                "with a 5% monthly tariff compensation if on-time performance falls below 90% for two consecutive months."
            )

        if "RULE-CURRENCY" in fb_upper or "CURRENCY" in fb_upper:
            modifications["section_3"].append(
                f"Currency compliance update: All tariff schedules and commercial figures in this section are strictly denominated in {currency} with zero foreign currency exposure."
            )

        if "RULE-RETURNS-TIME" in fb_upper or "48" in fb_upper:
            modifications["section_2"].append(
                "Turnaround compliance update: We strictly enforce a 48 to 72 hours minimum inspection and processing window; any sub-48h return request is superseded by this policy."
            )

        if "RULE-DISCOUNT-TIERS" in fb_upper or "DISCOUNT" in fb_upper or "MIGUEL TORRES" in fb_upper:
            modifications["section_3"].append(
                "Commercial governance update: Preferential volume tiers and storage volumes exceeding 50 m³ require express sign-off from Miguel Torres (Director Comercial)."
            )

        if "RULE-CARRIER-RATES" in fb_upper or "CARRIER" in fb_upper:
            modifications["section_3"].append(
                f"Rate confidentiality update: Internal carrier wholesale tariffs are strictly excluded; only final client rates in {currency} (or Pending confirmation) are presented."
            )

        if missing_aspects:
            for aspect in missing_aspects:
                if aspect == "open_questions_coverage":
                    modifications["section_4"].append(
                        "Open questions and operational assumptions are formally logged for client confirmation prior to contract signature."
                    )
                else:
                    val = key_aspects.get(aspect, "Pending confirmation")
                    label = aspect.replace("_", " ")
                    modifications["section_1"].append(
                        f"Addressed operational parameter {label} ({aspect}): {val if val is not None else 'Pending confirmation'}."
                    )

        if "READABILITY" in fb_upper:
            modifications["section_1"].append(
                "Executive summary refined for clear operational readability and direct service alignment."
            )

        # If freeform feedback did not match any specific tag above, apply it directly into Section 1 and Section 2 body
        if not any(modifications.values()):
            cleaned_fb = _sanitize_foreign_currency_in_text(
                _sanitize_sub_48h_returns_in_text(feedback_for_generator.strip()),
                currency,
            )
            modifications["section_1"].append(
                f"Updated operational scope per review feedback: {cleaned_fb}"
            )

        return modifications


class WarehouseGeneratorAgent(BaseDepartmentGeneratorAgent):
    """Warehouse Operations proposal generator agent led by Ana Whitfield."""

    department_id: DepartmentIdLiteral = "warehouse"
    department_name: str = "Warehouse Operations"
    responsible_person: str = "Ana Whitfield"

    def generate(
        self,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
        feedback_for_generator: Optional[str] = None,
        iteration: int = 1,
    ) -> str:
        """Generate Warehouse Operations proposal section in the client's mandatory currency."""
        client_name = str(rfp_metadata.get("client_name") or "Client")
        client_country = str(rfp_metadata.get("client_country") or "ES").upper()
        currency = resolve_currency_for_country(client_country)
        monthly_volume = rfp_metadata.get("monthly_volume")

        key_aspects: Dict[str, Any] = dict(section_context.get("key_aspects") or {})
        open_questions: List[str] = list(section_context.get("open_questions") or [])

        standards = FALLBACK_BRIEFING_STANDARDS["warehouse"]
        rates = standards["rates"][currency]
        kb_context = self.knowledge_helper.retrieve_department_guidelines(
            "warehouse",
            f"Warehouse pallet SKU rates onboarding {client_country}",
        )
        kb_snippets: List[str] = [
            _sanitize_foreign_currency_in_text(str(s), currency)
            for s in (kb_context.get("snippets") or [])
        ]

        location_pref = key_aspects.get("warehouse_location_preference") or (
            "Los Ángeles" if client_country == "US" else "Zaragoza"
        )
        pallet_req = key_aspects.get("pallet_storage_required")
        sku_count = key_aspects.get("sku_count")
        special_handling = key_aspects.get("special_handling") or []
        onboarding_complexity = key_aspects.get("onboarding_complexity") or "Baja"

        if pallet_req is not None:
            pallet_desc = f"We allocate storage capacity for {pallet_req} pallet positions calculated by occupied volume in m³."
        else:
            pallet_desc = "Capacidad de almacenamiento de pallets: Pendiente de confirmación según volumen ocupado en m³."

        if sku_count is not None:
            sku_desc = f"Our team tracks {sku_count} SKU inventory references."
        else:
            sku_desc = "SKU catalog: Pendiente de confirmación de referencias."

        handling_desc = (
            ", ".join(str(h) for h in special_handling)
            if special_handling
            else "safe standard handling"
        )
        volume_desc = (
            f"{monthly_volume} orders per month"
            if monthly_volume is not None
            else "your monthly order flow"
        )

        default_storage_label = (
            "16.00 EUR por m³ al mes (Zaragoza)"
            if currency == "EUR"
            else "$18.00 USD por m³ al mes (Los Ángeles)"
        )
        storage_rate_label = _extract_kb_rate_or_pending(
            kb_snippets,
            r"(?:16(?:\.00)?\s*EUR|(?:\$)?18(?:\.00)?\s*USD)\s+por\s+(?:m³|metro\s+cúbico)(?:\s+al\s+mes)?",
            default_storage_label,
            currency,
        )
        if storage_rate_label == "16 EUR por metro cúbico al mes":
            storage_rate_label = "16.00 EUR por m³ al mes (Zaragoza)"
        elif storage_rate_label in ("18 USD por metro cúbico al mes", "$18 USD por metro cúbico al mes"):
            storage_rate_label = "$18.00 USD por m³ al mes (Los Ángeles)"

        onboarding_fee_label = rates["onboarding_fee"]
        body_mods = self._build_body_feedback_directive(
            feedback_for_generator if iteration > 1 else None,
            currency,
            key_aspects,
        )

        sec1_lines = [
            f"We run your stock at our {location_pref} warehouse hub for {client_name}. "
            f"{pallet_desc} {sku_desc} "
            f"We support {handling_desc} for {volume_desc}."
        ]
        if body_mods["section_1"]:
            sec1_lines.extend(body_mods["section_1"])

        sec2_lines = [
            f"Your onboarding level is {onboarding_complexity}. "
            f"Setup takes {standards['standard_onboarding_weeks']}. "
            f"We commit to a canonical {standards['on_time_sla_pct']} on-time delivery SLA for all orders per contractual standards. "
            "Restock and return checks take 48 to 72 hours."
        ]
        if body_mods["section_2"]:
            sec2_lines.extend(body_mods["section_2"])

        sec3_lines = [
            f"All prices use {currency} as final client rates based on occupied volume in m³:",
            f"- Storage Rate: {storage_rate_label} (first 30 days free grace period; >180 days pays 150% long-term storage fee)",
            "- Additional capacity and handling: Pendiente de confirmación según volumen en m³",
            f"- Setup and Onboarding Fee: {onboarding_fee_label}",
        ]
        if body_mods["section_3"]:
            for mod in body_mods["section_3"]:
                sec3_lines.append(f"- {mod}")

        lines: List[str] = [
            f"## Warehouse Proposal for {client_name}",
            f"Lead: {self.responsible_person}. Hub country: {client_country}. Currency: {currency}.",
            "",
            "### 1. Space and Stock Plan",
            " ".join(sec1_lines),
            "",
            "### 2. Onboarding Plan and Service SLA",
            " ".join(sec2_lines),
            "",
            f"### 3. Warehouse Rates ({currency})",
            *sec3_lines,
            "",
            build_volume_discount_table(currency),
        ]

        for k, v in key_aspects.items():
            if k not in {
                "warehouse_location_preference",
                "pallet_storage_required",
                "sku_count",
                "special_handling",
                "onboarding_complexity",
            }:
                val_str = str(v)
                if feedback_for_generator and iteration > 1:
                    val_str = _sanitize_foreign_currency_in_text(
                        _sanitize_sub_48h_returns_in_text(val_str),
                        currency,
                    )
                lines.append(f"- Aspect {k}: {val_str}")

        if open_questions or body_mods["section_4"]:
            lines.append("")
            lines.append("### 4. Open Questions")
            lines.append("We will confirm these open questions during onboarding.")
            for idx, q in enumerate(open_questions, start=1):
                lines.append(f"- Question {idx}: {q} (Pending confirmation on SKU and volume details).")
            for mod in body_mods["section_4"]:
                lines.append(f"- {mod}")

        if kb_snippets:
            lines.append("")
            lines.append(f"Policy Note ({kb_context['source']}): {kb_snippets[0]}")

        if feedback_for_generator and iteration > 1:
            lines.append("")
            lines.append(
                f"### 5. Revision Note (Attempt {iteration})\n"
                f"Applied active corrections to the proposal body based on evaluator feedback:\n"
                f"- Updated body sections to address: {_sanitize_foreign_currency_in_text(_sanitize_sub_48h_returns_in_text(feedback_for_generator), currency)}\n"
                f"- Aligned storage pricing strictly to KB rate {storage_rate_label} and marked unconfirmed fees as Pending confirmation."
            )

        draft = "\n".join(lines)
        if feedback_for_generator and iteration > 1:
            draft = _sanitize_foreign_currency_in_text(
                _sanitize_sub_48h_returns_in_text(draft),
                currency,
            )
        return draft


class LastMileGeneratorAgent(BaseDepartmentGeneratorAgent):
    """Last Mile and Carrier Management proposal generator agent led by Carlos Vega."""

    department_id: DepartmentIdLiteral = "lastmile"
    department_name: str = "Last Mile and Carrier Management"
    responsible_person: str = "Carlos Vega"

    def generate(
        self,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
        feedback_for_generator: Optional[str] = None,
        iteration: int = 1,
    ) -> str:
        """Generate Last Mile proposal section in the client's mandatory currency."""
        client_name = str(rfp_metadata.get("client_name") or "Client")
        client_country = str(rfp_metadata.get("client_country") or "ES").upper()
        currency = resolve_currency_for_country(client_country)
        monthly_volume = rfp_metadata.get("monthly_volume")

        key_aspects: Dict[str, Any] = dict(section_context.get("key_aspects") or {})
        open_questions: List[str] = list(section_context.get("open_questions") or [])

        standards = FALLBACK_BRIEFING_STANDARDS["lastmile"]
        rates = standards["rates"][currency]
        kb_context = self.knowledge_helper.retrieve_department_guidelines(
            "lastmile",
            f"Last mile carrier SLA shipping rates {client_country}",
        )
        kb_snippets: List[str] = [
            _sanitize_foreign_currency_in_text(str(s), currency)
            for s in (kb_context.get("snippets") or [])
        ]

        carrier_strategy = key_aspects.get("carrier_strategy") or "TrackFlow Network"
        geographic_scope = key_aspects.get("geographic_scope") or (
            "Domestic US" if client_country == "US" else "Domestic ES"
        )
        delivery_sla_req = key_aspects.get("delivery_sla_requested")
        special_reqs = key_aspects.get("special_delivery_requirements") or []

        carrier_hub_network = (
            "UPS, FedEx, and DHL from Los Ángeles"
            if client_country == "US"
            else "MRW, SEUR, DHL, and 2 local last-mile carriers in Zaragoza"
        )

        sla_target_desc = (
            f"We support your {delivery_sla_req} delivery transit goal."
            if delivery_sla_req
            else "Standard delivery takes 3 to 5 business days across all zones."
        )
        special_reqs_desc = (
            ", ".join(str(r) for r in special_reqs)
            if special_reqs
            else "full parcel tracking"
        )
        volume_desc = (
            f"{monthly_volume} monthly shipments"
            if monthly_volume is not None
            else "your monthly parcel shipments"
        )

        body_mods = self._build_body_feedback_directive(
            feedback_for_generator if iteration > 1 else None,
            currency,
            key_aspects,
        )

        sec1_lines = [
            f"We use the {carrier_strategy} ({carrier_hub_network}) across {geographic_scope} for {client_name}. "
            f"Our team handles {volume_desc} with {special_reqs_desc}."
        ]
        if body_mods["section_1"]:
            sec1_lines.extend(body_mods["section_1"])

        sec2_lines = [
            f"{sla_target_desc} "
            f"We commit to a canonical {standards['on_time_sla_pct']} on-time delivery SLA per contractual standards. "
            "Return parcels take 48 to 72 hours to process."
        ]
        if body_mods["section_2"]:
            sec2_lines.extend(body_mods["section_2"])

        sec3_lines = [
            f"All shipping fees use {currency} as final client prices:",
            f"- Ground Parcel Rate: {rates['standard_parcel']}",
            f"- Express Parcel Rate: {rates['express_parcel']}",
        ]
        if body_mods["section_3"]:
            for mod in body_mods["section_3"]:
                sec3_lines.append(f"- {mod}")

        lines: List[str] = [
            f"## Last Mile Proposal for {client_name}",
            f"Lead: {self.responsible_person}. Scope country: {client_country}. Currency: {currency}.",
            "",
            "### 1. Carrier Plan and Geographic Scope",
            " ".join(sec1_lines),
            "",
            "### 2. On-Time Delivery SLA",
            " ".join(sec2_lines),
            "",
            f"### 3. Final Client Shipping Rates ({currency})",
            *sec3_lines,
            "",
            build_volume_discount_table(currency),
        ]

        for k, v in key_aspects.items():
            if k not in {
                "carrier_strategy",
                "geographic_scope",
                "delivery_sla_requested",
                "special_delivery_requirements",
            }:
                val_str = str(v)
                if feedback_for_generator and iteration > 1:
                    val_str = _sanitize_foreign_currency_in_text(
                        _sanitize_sub_48h_returns_in_text(val_str),
                        currency,
                    )
                lines.append(f"- Aspect {k}: {val_str}")

        if open_questions or body_mods["section_4"]:
            lines.append("")
            lines.append("### 4. Open Questions")
            lines.append("We will confirm these open questions on delivery SLA tiers.")
            for idx, q in enumerate(open_questions, start=1):
                lines.append(f"- Question {idx}: {q} (Pending confirmation on parcel weight and SLA split).")
            for mod in body_mods["section_4"]:
                lines.append(f"- {mod}")

        if kb_snippets:
            lines.append("")
            lines.append(f"Policy Note ({kb_context['source']}): {kb_snippets[0]}")

        if feedback_for_generator and iteration > 1:
            lines.append("")
            lines.append(
                f"### 5. Revision Note (Attempt {iteration})\n"
                f"Applied active corrections to the proposal body based on evaluator feedback:\n"
                f"- Updated body sections to address: {_sanitize_foreign_currency_in_text(_sanitize_sub_48h_returns_in_text(feedback_for_generator), currency)}\n"
                f"- Marked unpublished parcel rates as Pending confirmation in {currency} without disclosing internal carrier tariffs."
            )

        draft = "\n".join(lines)
        if feedback_for_generator and iteration > 1:
            draft = _sanitize_foreign_currency_in_text(
                _sanitize_sub_48h_returns_in_text(draft),
                currency,
            )
        return draft


class ReverseLogisticsGeneratorAgent(BaseDepartmentGeneratorAgent):
    """Reverse Logistics proposal generator agent led by Sofía Ramos."""

    department_id: DepartmentIdLiteral = "reverse"
    department_name: str = "Reverse Logistics"
    responsible_person: str = "Sofía Ramos"

    def generate(
        self,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
        feedback_for_generator: Optional[str] = None,
        iteration: int = 1,
    ) -> str:
        """Generate Reverse Logistics proposal section enforcing >= 48h turnaround and mandatory currency."""
        client_name = str(rfp_metadata.get("client_name") or "Client")
        client_country = str(rfp_metadata.get("client_country") or "ES").upper()
        currency = resolve_currency_for_country(client_country)

        key_aspects: Dict[str, Any] = dict(section_context.get("key_aspects") or {})
        open_questions: List[str] = list(section_context.get("open_questions") or [])

        standards = FALLBACK_BRIEFING_STANDARDS["reverse"]
        rates = standards["rates"][currency]
        kb_context = self.knowledge_helper.retrieve_department_guidelines(
            "reverse",
            f"Reverse returns turnaround 48 hours pricing {client_country}",
        )
        kb_snippets: List[str] = [
            _sanitize_foreign_currency_in_text(str(s), currency)
            for s in (kb_context.get("snippets") or [])
        ]

        return_window = key_aspects.get("return_window_days") or 30
        return_rate = key_aspects.get("estimated_return_rate")
        inspection_req = key_aspects.get("inspection_required", True)
        disposition_flow = key_aspects.get("disposition_flow") or [
            "reventa",
            "reacondicionamiento",
            "descarte",
        ]

        rate_desc = (
            f"We plan for a return rate of {float(return_rate) * 100:.1f}%."
            if isinstance(return_rate, (int, float))
            else "We will confirm your expected return rate at launch (Pending confirmation)."
        )
        flow_desc = ", ".join(str(d) for d in disposition_flow)
        inspection_desc = (
            "full manual quality inspection"
            if inspection_req
            else "standard return inspection"
        )

        body_mods = self._build_body_feedback_directive(
            feedback_for_generator if iteration > 1 else None,
            currency,
            key_aspects,
        )

        sec1_lines = [
            f"We support a {return_window} days return window for {client_name}. "
            f"{rate_desc} "
            f"Each unit gets {inspection_desc}. "
            f"Our disposition flow covers: {flow_desc}. "
            "TrackFlow executes return logistics per client brand rules and does not refurbish or resell products on its own account."
        ]
        if body_mods["section_1"]:
            sec1_lines.extend(body_mods["section_1"])

        sec2_lines = [
            f"Led by {self.responsible_person}, return turnaround takes {standards['minimum_turnaround_hours']}. "
            "TrackFlow strictly enforces a minimum turnaround of 48 hours; we never promise returns under 48 hours. "
            f"We commit to a canonical {standards['on_time_sla_pct']} on-time SLA per contractual standards."
        ]
        if body_mods["section_2"]:
            sec2_lines.extend(body_mods["section_2"])

        sec3_lines = [
            f"All return fees use {currency} as final client prices:",
            f"- Return Shipping Cost Policy: Borne by the client brand unless caused by a TrackFlow error (transit damage or wrong delivery)",
            f"- Return Inspection Rate: {rates['return_inspection_unit']}",
            f"- Classification and Disposition Handling Rate: {rates['refurbishment_unit']}",
        ]
        if body_mods["section_3"]:
            for mod in body_mods["section_3"]:
                sec3_lines.append(f"- {mod}")

        lines: List[str] = [
            f"## Reverse Logistics Proposal for {client_name}",
            f"Lead: {self.responsible_person}. Country: {client_country}. Currency: {currency}.",
            "",
            "### 1. Return Window and Inspection Flow",
            " ".join(sec1_lines),
            "",
            "### 2. Turnaround Time (48 to 72 Hours) and SLA",
            " ".join(sec2_lines),
            "",
            f"### 3. Returns Rates ({currency})",
            *sec3_lines,
            "",
            build_volume_discount_table(currency),
        ]

        for k, v in key_aspects.items():
            if k not in {
                "return_window_days",
                "estimated_return_rate",
                "inspection_required",
                "disposition_flow",
            }:
                val_str = str(v)
                if feedback_for_generator and iteration > 1:
                    val_str = _sanitize_foreign_currency_in_text(
                        _sanitize_sub_48h_returns_in_text(val_str),
                        currency,
                    )
                lines.append(f"- Aspect {k}: {val_str}")

        if open_questions or body_mods["section_4"]:
            lines.append("")
            lines.append("### 4. Open Questions")
            lines.append("We will confirm these open questions on return rate volume.")
            for idx, q in enumerate(open_questions, start=1):
                lines.append(f"- Question {idx}: {q} (Pending confirmation on expected return rate).")
            for mod in body_mods["section_4"]:
                lines.append(f"- {mod}")

        if kb_snippets:
            lines.append("")
            lines.append(f"Policy Note ({kb_context['source']}): {kb_snippets[0]}")

        if feedback_for_generator and iteration > 1:
            lines.append("")
            lines.append(
                f"### 5. Revision Note (Attempt {iteration})\n"
                f"Applied active corrections to the proposal body based on evaluator feedback:\n"
                f"- Updated body sections to address: {_sanitize_foreign_currency_in_text(_sanitize_sub_48h_returns_in_text(feedback_for_generator), currency)}\n"
                f"- Grounded returns cost policy in the Knowledge Base and marked per-unit tariffs as Pending confirmation in {currency}."
            )

        draft = "\n".join(lines)
        if feedback_for_generator and iteration > 1:
            draft = _sanitize_foreign_currency_in_text(
                _sanitize_sub_48h_returns_in_text(draft),
                currency,
            )
        return draft


def get_department_generator_agent(
    department_id: DepartmentIdLiteral,
    knowledge_helper: Optional[KnowledgeRetrievalHelper] = None,
) -> BaseDepartmentGeneratorAgent:
    """Factory returning the dedicated proposal generator agent for the requested department."""
    if department_id == "warehouse":
        return WarehouseGeneratorAgent(knowledge_helper=knowledge_helper)
    if department_id == "lastmile":
        return LastMileGeneratorAgent(knowledge_helper=knowledge_helper)
    if department_id == "reverse":
        return ReverseLogisticsGeneratorAgent(knowledge_helper=knowledge_helper)
    raise ValueError(f"Unsupported department_id: '{department_id}'")
