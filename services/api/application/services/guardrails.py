"""Business constraint and policy guardrail validator for TrackFlow Knowledge Base.

Enforces non-negotiable commercial governance rules (FR-012, SC-005):
1. Volume storage discounts (>50 m³) require Commercial Director Miguel Torres's approval;
   account managers cannot offer or grant discounts independently.
2. Delivery SLAs are never guaranteed during declared peak dates (Black Friday, Christmas,
   January Sales in Spain); delivery times may extend by up to 40% and must be
   communicated proactively in advance.
3. International cross-border returns are not automated and require manual handling by
   Sofía Ramos's team (Returns Manager / Reverse Logistics).
4. Carrier assignment is automated by the system; manual carrier selection or exceptions
   require approval from Carlos Vega (Head of Carrier Operations).
"""

import re
from dataclasses import dataclass
from typing import List

from domain.knowledge.entities import RetrievedContext


@dataclass(frozen=True)
class GuardrailCheckResult:
    """Result of evaluating a synthesized answer against TrackFlow business guardrails."""

    rule_id: str
    triggered: bool
    compliant: bool
    remediation_clause: str


class BusinessGuardrailValidator:
    """Evaluates and enforces TrackFlow corporate governance rules on generated answers."""

    VOLUME_DISCOUNT_CLAUSE = (
        "Clients with more than 50 cubic meters of average monthly volume qualify to "
        "negotiate a preferential storage rate; however, any discount negotiation must "
        "always go through and receive formal approval from Commercial Director Miguel Torres "
        "— an account manager cannot offer or approve storage discounts independently on their own."
    )

    PEAK_SEASON_SLA_CLAUSE = (
        "Important SLA Guardrail: TrackFlow does not guarantee standard delivery SLAs "
        "(including the 90% monthly on-time commitment) during declared high-demand peak dates "
        "(Black Friday, Christmas, and January Sales in Spain). During these peak periods, "
        "delivery timelines may extend by up to an additional 40%, and this extension must "
        "be communicated proactively to clients in advance."
    )

    INTERNATIONAL_RETURNS_CLAUSE = (
        "International returns (items purchased in one country and returned in another) are "
        "not covered by the standard automated returns pipeline and require manual handling "
        "and coordination by Sofía Ramos's team (Returns Manager / Reverse Logistics)."
    )

    CARRIER_OVERRIDE_CLAUSE = (
        "Carrier selection for each shipment is automatically determined by the routing system "
        "based on destination, weight, product type, and urgency; an account manager does not "
        "manually choose or override the carrier except for an exception formally approved by "
        "Carlos Vega (Head of Carrier Operations)."
    )

    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[RetrievedContext],
    ) -> List[GuardrailCheckResult]:
        """Evaluate which business guardrails apply to the query/context and whether the answer complies.

        Args:
            query: User's natural language question.
            answer: Candidate synthesized answer string.
            contexts: Retrieved context chunks.

        Returns:
            List of GuardrailCheckResult objects for all 4 corporate guardrails.
        """
        combined_input = self._build_trigger_surface(query, contexts)
        lowered_answer = answer.lower()

        results: List[GuardrailCheckResult] = []

        # 1. Storage Volume Discount Guardrail (Miguel Torres)
        vol_triggered = self._is_volume_discount_triggered(combined_input)
        vol_compliant = (
            not vol_triggered
            or (
                "miguel torres" in lowered_answer
                and "50" in lowered_answer
                and ("cannot" in lowered_answer or "not " in lowered_answer)
            )
        )
        results.append(
            GuardrailCheckResult(
                rule_id="storage_volume_discount_miguel_torres",
                triggered=vol_triggered,
                compliant=vol_compliant,
                remediation_clause=self.VOLUME_DISCOUNT_CLAUSE,
            )
        )

        # 2. Peak Season SLA Guardrail (Black Friday / Christmas / January Sales / +40%)
        peak_triggered = self._is_peak_season_triggered(combined_input)
        peak_compliant = (
            not peak_triggered
            or (
                "40%" in lowered_answer
                and ("not guarantee" in lowered_answer or "not guaranteed" in lowered_answer)
                and "advance" in lowered_answer
            )
        )
        results.append(
            GuardrailCheckResult(
                rule_id="peak_season_sla_extension",
                triggered=peak_triggered,
                compliant=peak_compliant,
                remediation_clause=self.PEAK_SEASON_SLA_CLAUSE,
            )
        )

        # 3. International Cross-Border Returns Guardrail (Sofía Ramos)
        intl_return_triggered = self._is_international_return_triggered(combined_input)
        intl_return_compliant = (
            not intl_return_triggered
            or (
                ("sofía ramos" in lowered_answer or "sofia ramos" in lowered_answer)
                and "manual" in lowered_answer
            )
        )
        results.append(
            GuardrailCheckResult(
                rule_id="international_returns_sofia_ramos",
                triggered=intl_return_triggered,
                compliant=intl_return_compliant,
                remediation_clause=self.INTERNATIONAL_RETURNS_CLAUSE,
            )
        )

        # 4. Carrier Override / Selection Guardrail (Carlos Vega)
        carrier_triggered = self._is_carrier_exception_triggered(query.lower(), combined_input)
        carrier_compliant = (
            not carrier_triggered
            or (
                "carlos vega" in lowered_answer
                and ("system" in lowered_answer or "automat" in lowered_answer)
            )
        )
        results.append(
            GuardrailCheckResult(
                rule_id="carrier_override_carlos_vega",
                triggered=carrier_triggered,
                compliant=carrier_compliant,
                remediation_clause=self.CARRIER_OVERRIDE_CLAUSE,
            )
        )

        return results

    def enforce(
        self,
        query: str,
        answer: str,
        contexts: List[RetrievedContext],
    ) -> str:
        """Enforce all triggered corporate guardrails on the candidate answer.

        If a leading question attempts to assert that account managers can independently
        approve discounts or promise peak-season SLAs, counters the false premise and
        injects the required contractual guardrail clause.

        Args:
            query: User's natural language inquiry.
            answer: Candidate answer text.
            contexts: Retrieved context chunks.

        Returns:
            Guardrail-compliant answer string.
        """
        checks = self.evaluate(query=query, answer=answer, contexts=contexts)
        enforced_answer = answer.strip()

        for check in checks:
            if check.triggered and not check.compliant:
                if enforced_answer:
                    enforced_answer = f"{enforced_answer} {check.remediation_clause}"
                else:
                    enforced_answer = check.remediation_clause

        return enforced_answer

    @staticmethod
    def _build_trigger_surface(query: str, contexts: List[RetrievedContext]) -> str:
        """Combine query and top retrieved chunk text for trigger evaluation."""
        top_text = contexts[0].chunk.text if contexts else ""
        return f"{query}\n{top_text}".lower()

    @staticmethod
    def _is_volume_discount_triggered(surface: str) -> bool:
        """Detect storage volume discount or preferential rate queries."""
        keywords = [
            "discount",
            "descuento",
            "preferential rate",
            "miguel torres",
            "50 cubic meters",
            "75 cubic meters",
            "50 m³",
            "50 m3",
        ]
        if any(kw in surface for kw in keywords):
            return True
        return bool(re.search(r"\b([5-9]\d|\d{3,})\s*(cubic meters|m3|m³)", surface))

    @staticmethod
    def _is_peak_season_triggered(surface: str) -> bool:
        """Detect peak demand / holiday SLA commitment queries."""
        keywords = [
            "black friday",
            "christmas",
            "january sales",
            "high-demand",
            "high demand",
            "peak season",
            "peak demand",
            "holiday sales",
            "rebajas de enero",
            "navidad",
        ]
        return any(kw in surface for kw in keywords)

    @staticmethod
    def _is_international_return_triggered(surface: str) -> bool:
        """Detect international or cross-border return inquiries."""
        keywords = [
            "international return",
            "cross-border return",
            "cross border return",
            "purchased in one country",
            "returned in another",
            "purchased in the us and returned in spain",
            "sofía ramos",
            "sofia ramos",
            "devolución internacional",
            "devoluciones internacionales",
        ]
        return any(kw in surface for kw in keywords)

    @staticmethod
    def _is_carrier_exception_triggered(query_lower: str, surface: str) -> bool:
        """Detect carrier selection override or exception inquiries."""
        keywords = [
            "carlos vega",
            "manually choose",
            "manual carrier",
            "override carrier",
            "carrier override",
            "carrier exception",
            "choose the carrier",
            "select the carrier",
            "carrier selection",
        ]
        return any(kw in query_lower or kw in surface for kw in keywords)
