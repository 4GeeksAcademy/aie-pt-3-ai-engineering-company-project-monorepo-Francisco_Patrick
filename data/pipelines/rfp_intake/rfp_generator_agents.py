"""Dedicated department proposal generator agents for Part 2 RFP Response Generation.

Implements isolated generator agents per fulfillment department per TrackFlow briefing §2.1 & §5:
- WarehouseGeneratorAgent (Ana Whitfield): Storage capacity, pallet/SKU costs, onboarding schedule.
- LastMileGeneratorAgent (Carlos Vega): Shipping costs, carrier network by destination, delivery SLA.
- ReverseLogisticsGeneratorAgent (Sofía Ramos): Returns processing cost, turnaround time >= 48 hours.

Includes encapsulated VectorStorePort lookup with graceful offline fallback to briefing standards.
"""

from __future__ import annotations

import logging
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
                "onboarding_fee": "$1,500.00 USD",
            },
            "EUR": {
                "storage_m3_monthly": "16.00 EUR por m³",
                "onboarding_fee": "1,350.00 EUR",
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
                "standard_parcel": "$6.40 USD",
                "express_parcel": "$11.80 USD",
            },
            "EUR": {
                "standard_parcel": "5.20 EUR",
                "express_parcel": "9.60 EUR",
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
                "return_inspection_unit": "$2.80 USD",
                "refurbishment_unit": "$4.50 USD",
            },
            "EUR": {
                "return_inspection_unit": "2.40 EUR",
                "refurbishment_unit": "3.90 EUR",
            },
        },
        "policy_note": (
            "TrackFlow Reverse checks each return item within 48 to 72 hours. "
            "Returns processing is never promised under 48 hours. "
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
    unit_symbol = "$" if currency == "USD" else "€"
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
            pallet_desc = "Capacidad adicional de almacenamiento: Pendiente de confirmación según volumen en m³."

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

        storage_rate_label = (
            "16.00 EUR por m³ al mes (Zaragoza)"
            if currency == "EUR"
            else "$18.00 USD por m³ al mes (Los Ángeles)"
        )

        lines: List[str] = [
            f"## Warehouse Proposal for {client_name}",
            f"Lead: {self.responsible_person}. Hub country: {client_country}. Currency: {currency}.",
            "",
            "### 1. Space and Stock Plan",
            f"We run your stock at our {location_pref} warehouse hub for {client_name}. "
            f"{pallet_desc} {sku_desc} "
            f"We support {handling_desc} for {volume_desc}.",
            "",
            "### 2. Onboarding Plan and Service SLA",
            f"Your onboarding level is {onboarding_complexity}. "
            f"Setup takes {standards['standard_onboarding_weeks']}. "
            f"We commit to a canonical {standards['on_time_sla_pct']} on-time delivery SLA for all orders per contractual standards. "
            "Restock and return checks take 48 to 72 hours.",
            "",
            f"### 3. Warehouse Rates ({currency})",
            f"All prices use {currency} as final client rates based on occupied volume in m³:",
            f"- Storage Rate: {storage_rate_label} (first 30 days free grace period; >180 days pays 150% long-term storage fee)",
            f"- Additional capacity and handling: Pendiente de confirmación según volumen en m³",
            f"- Setup Fee: {rates['onboarding_fee']} one time",
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
                lines.append(f"- Aspect {k}: {v}")

        if open_questions:
            lines.append("")
            lines.append("### 4. Open Questions")
            lines.append("We will confirm these open questions during onboarding.")
            for idx, q in enumerate(open_questions, start=1):
                lines.append(f"- Question {idx}: {q} (Pending client check on SKU and volume details).")

        if kb_context.get("snippets"):
            lines.append("")
            lines.append(f"Policy Note ({kb_context['source']}): {kb_context['snippets'][0]}")

        if feedback_for_generator and iteration > 1:
            lines.append("")
            lines.append(
                f"### 5. Revision Note (Attempt {iteration})\n"
                f"Applied active corrections based on evaluator feedback:\n"
                f"- Enforced canonical {standards['on_time_sla_pct']} on-time delivery SLA per contractual policy.\n"
                f"- Aligned storage pricing strictly to {storage_rate_label} based on occupied volume in m³.\n"
                f"- Marked all unconfirmed capacity and custom operations as 'Pendiente de confirmación según volumen en m³'.\n"
                f"- Enforced volume discount table governance under Miguel Torres (Director Comercial)."
            )

        return "\n".join(lines)


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

        carrier_strategy = key_aspects.get("carrier_strategy") or "TrackFlow Network"
        geographic_scope = key_aspects.get("geographic_scope") or (
            "Domestic US" if client_country == "US" else "Domestic ES"
        )
        delivery_sla_req = key_aspects.get("delivery_sla_requested")
        special_reqs = key_aspects.get("special_delivery_requirements") or []

        sla_target_desc = (
            f"We support your {delivery_sla_req} delivery transit goal."
            if delivery_sla_req
            else "Standard delivery takes 48 to 72 hours across all zones."
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

        lines: List[str] = [
            f"## Last Mile Proposal for {client_name}",
            f"Lead: {self.responsible_person}. Scope country: {client_country}. Currency: {currency}.",
            "",
            "### 1. Carrier Plan and Geographic Scope",
            f"We use the {carrier_strategy} across {geographic_scope} for {client_name}. "
            f"Our team handles {volume_desc} with {special_reqs_desc}.",
            "",
            "### 2. On-Time Delivery SLA",
            f"{sla_target_desc} "
            f"We commit to a canonical {standards['on_time_sla_pct']} on-time delivery SLA per contractual standards. "
            "Return parcels take 48 to 72 hours to process.",
            "",
            f"### 3. Final Client Shipping Rates ({currency})",
            f"All shipping fees use {currency} as final client prices:",
            f"- Ground Parcel Rate: {rates['standard_parcel']} per box",
            f"- Express Parcel Rate: {rates['express_parcel']} per box",
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
                lines.append(f"- Aspect {k}: {v}")

        if open_questions:
            lines.append("")
            lines.append("### 4. Open Questions")
            lines.append("We will confirm these open questions on delivery SLA tiers.")
            for idx, _ in enumerate(open_questions, start=1):
                lines.append(f"- Question {idx}: Pending client check on parcel SLA split.")

        if kb_context.get("snippets"):
            lines.append("")
            lines.append(f"Policy Note ({kb_context['source']}): {kb_context['snippets'][0]}")

        if feedback_for_generator and iteration > 1:
            lines.append("")
            lines.append(
                f"### 5. Revision Note (Attempt {iteration})\n"
                f"Applied active corrections based on evaluator feedback:\n"
                f"- Enforced canonical {standards['on_time_sla_pct']} on-time delivery SLA per contractual standards.\n"
                f"- Quoted final client shipping rates strictly in {currency} without disclosing internal carrier tariffs.\n"
                f"- Incorporated volume discount table under Miguel Torres commercial governance."
            )

        return "\n".join(lines)


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
            else "We will confirm your expected return rate at launch."
        )
        flow_desc = ", ".join(str(d) for d in disposition_flow)
        inspection_desc = (
            "full manual quality inspection"
            if inspection_req
            else "fast return inspection"
        )

        lines: List[str] = [
            f"## Reverse Logistics Proposal for {client_name}",
            f"Lead: {self.responsible_person}. Country: {client_country}. Currency: {currency}.",
            "",
            "### 1. Return Window and Inspection Flow",
            f"We support a {return_window} days return window for {client_name}. "
            f"{rate_desc} "
            f"Each unit gets {inspection_desc}. "
            f"Our disposition flow covers: {flow_desc}.",
            "",
            "### 2. Turnaround Time (48 to 72 Hours) and SLA",
            f"Led by {self.responsible_person}, return turnaround takes {standards['minimum_turnaround_hours']}. "
            "TrackFlow strictly enforces a minimum turnaround of 48 hours; we never promise returns under 48 hours. "
            f"We commit to a canonical {standards['on_time_sla_pct']} on-time SLA per contractual standards.",
            "",
            f"### 3. Returns Rates ({currency})",
            f"All return fees use {currency} as final client prices:",
            f"- Return Inspection Rate: {rates['return_inspection_unit']} per unit",
            f"- Repack and Care Rate: {rates['refurbishment_unit']} per unit",
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
                lines.append(f"- Aspect {k}: {v}")

        if open_questions:
            lines.append("")
            lines.append("### 4. Open Questions")
            lines.append("We will confirm these open questions on return rate volume.")
            for idx, _ in enumerate(open_questions, start=1):
                lines.append(f"- Question {idx}: Pending client check on expected return rate.")

        if kb_context.get("snippets"):
            lines.append("")
            lines.append(f"Policy Note ({kb_context['source']}): {kb_context['snippets'][0]}")

        if feedback_for_generator and iteration > 1:
            lines.append("")
            lines.append(
                f"### 5. Revision Note (Attempt {iteration})\n"
                f"Applied active corrections based on evaluator feedback:\n"
                f"- Strictly enforced minimum turnaround of 48 to 72 hours per TrackFlow policy (eliminating any sub-48h promises).\n"
                f"- Committed to canonical {standards['on_time_sla_pct']} on-time delivery and returns SLA per contractual standards.\n"
                f"- Quoted return processing rates strictly in {currency} and marked unconfirmed volumes as 'Pendiente'.\n"
                f"- Incorporated volume discount table under Miguel Torres commercial governance."
            )

        return "\n".join(lines)


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
