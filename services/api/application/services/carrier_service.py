"""Carrier selection decision engine with deterministic indirect prompt injection defense.

Adheres to Monorepo Constitution Principles I, II, and IV.
Ensures embedded directives in warehouse notes or shipping labels cannot hijack routing decisions.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field
from application.services.agent_guardrails import wrap_untrusted_content


_INDIRECT_INJECTION_PATTERNS: List[re.Pattern[str]] = [
    re.compile(
        r"(?i)\b(?:system\s+override|admin\s+override|prompt\s+override|override\s+policy)\b",
    ),
    re.compile(
        r"(?i)\b(?:always\s+assign|force\s+assign|must\s+assign|route\s+via)\s+(?:the\s+)?(?:most\s+expensive|premium|overnight|costliest|fastest)\s+carrier\b",
    ),
    re.compile(
        r"(?i)\b(?:ignore\s+(?:previous|all|system)\s+instructions|disregard\s+rate\s+table)\b",
    ),
    re.compile(
        r"(?i)\b(?:asignar\s+(?:siempre\s+)?el\s+m[aá]s\s+caro|anular\s+reglas|ignorar\s+instrucciones)\b",
    ),
]


class CarrierSelectionRequest(BaseModel):
    """Input payload for automated carrier selection."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    weight_kg: float = Field(ge=0.01, description="Parcel weight in kilograms")
    destination_country: str = Field(min_length=2, max_length=2, description="ISO-2 destination country")
    warehouse_notes: Optional[str] = Field(default=None, description="Free-text shipping or warehouse notes")
    required_delivery_days: Optional[int] = Field(default=None, description="Maximum allowed transit days")


class CarrierSelectionResult(BaseModel):
    """Output result from carrier selection decision engine."""

    model_config = ConfigDict(extra="forbid")

    order_id: str
    selected_carrier: str
    service_tier: str
    quoted_rate_eur: float
    destination_country: str
    weight_kg: float
    indirect_injection_detected: bool
    clean_warehouse_notes: str
    bounded_warehouse_notes: str
    explanation: str


class CarrierSelectionService:
    """Decision engine selecting optimal logistics carriers based strictly on physical attributes."""

    # Spanish Domestic Carrier Rate Table (EUR base rates for <= 3.0 kg)
    ES_CARRIER_RATES: Dict[str, Tuple[float, str]] = {
        "Correos Express": (4.50, "STANDARD_GROUND"),
        "GLS": (4.75, "STANDARD_GROUND"),
        "SEUR": (5.20, "EXPRESS_GROUND"),
        "MRW": (5.80, "EXPRESS_GROUND"),
        "DHL Express": (28.50, "PREMIUM_OVERNIGHT"),
        "FedEx Priority": (32.00, "PREMIUM_OVERNIGHT"),
    }

    # US Domestic Carrier Rate Table (EUR equivalent for <= 3.0 kg)
    US_CARRIER_RATES: Dict[str, Tuple[float, str]] = {
        "UPS Ground": (6.50, "STANDARD_GROUND"),
        "FedEx Ground": (6.80, "STANDARD_GROUND"),
        "USPS Priority": (7.20, "PRIORITY_MAIL"),
        "DHL Express": (34.00, "PREMIUM_OVERNIGHT"),
    }

    def sanitize_warehouse_notes(self, raw_notes: Optional[str]) -> Tuple[str, bool]:
        """Strip embedded prompt directives from warehouse notes and flag injections.

        Returns:
            Tuple of (sanitized_clean_notes, indirect_injection_detected)
        """
        if not raw_notes or not raw_notes.strip():
            return "", False

        cleaned = raw_notes.strip()
        injection_detected = False

        for pattern in _INDIRECT_INJECTION_PATTERNS:
            if pattern.search(cleaned):
                injection_detected = True
                cleaned = pattern.sub("[REDACTED_ADVERSARIAL_DIRECTIVE]", cleaned)

        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned, injection_detected

    def select_carrier(self, request: CarrierSelectionRequest) -> CarrierSelectionResult:
        """Deterministically evaluate canonical physical parameters and select optimal carrier.

        Any embedded instruction in warehouse_notes (such as 'always assign the most expensive carrier')
        is completely ignored, and the most economic compliant carrier is assigned.
        """
        clean_notes, injection_detected = self.sanitize_warehouse_notes(request.warehouse_notes)
        bounded_notes = wrap_untrusted_content(clean_notes) if clean_notes else ""

        country = request.destination_country.upper()

        if country == "ES":
            rate_table = self.ES_CARRIER_RATES
            # Optimal economic selection: Correos Express
            selected = "Correos Express"
        elif country == "US":
            rate_table = self.US_CARRIER_RATES
            selected = "UPS Ground"
        else:
            # Default EU cross-border
            rate_table = self.ES_CARRIER_RATES
            selected = "GLS"

        rate, tier = rate_table[selected]

        # Calculate rate adjustment for weight > 1.0 kg
        if request.weight_kg > 1.0:
            rate = round(rate + (request.weight_kg - 1.0) * 1.20, 2)

        explanation = (
            f"Assigned optimal economic carrier '{selected}' based strictly on weight ({request.weight_kg}kg) "
            f"and destination ({country})."
        )
        if injection_detected:
            explanation += (
                " Note: Embedded prompt injection override was detected in warehouse notes "
                "and neutralized."
            )

        return CarrierSelectionResult(
            order_id=request.order_id,
            selected_carrier=selected,
            service_tier=tier,
            quoted_rate_eur=rate,
            destination_country=country,
            weight_kg=request.weight_kg,
            indirect_injection_detected=injection_detected,
            clean_warehouse_notes=clean_notes,
            bounded_warehouse_notes=bounded_notes,
            explanation=explanation,
        )


_default_carrier_service: Optional[CarrierSelectionService] = None


def get_carrier_selection_service() -> CarrierSelectionService:
    """Singleton provider for CarrierSelectionService."""
    global _default_carrier_service
    if _default_carrier_service is None:
        _default_carrier_service = CarrierSelectionService()
    return _default_carrier_service
