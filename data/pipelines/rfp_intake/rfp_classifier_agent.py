"""Classifier Agent for evaluating document validity and screening genuine RFPs vs solicitations."""

from dataclasses import dataclass
import re
from typing import Optional


@dataclass(frozen=True)
class ClassificationDecision:
    """Outcome of document validity screening."""

    is_rfp: bool
    rejection_reason: Optional[str] = None


class RFPClassifierAgent:
    """Screens ingested documents to determine whether they are genuine customer RFPs.

    Discards carrier sales pitches, transportation vendor rate cards, and unrelated spam.
    """

    def classify(self, markdown_content: str) -> ClassificationDecision:
        """Classify document markdown content.

        Args:
            markdown_content: Extracted markdown text from the proposal document.

        Returns:
            ClassificationDecision containing validity flag and rejection reason if invalid.
        """
        text = (markdown_content or "").strip()
        if not text:
            return ClassificationDecision(
                is_rfp=False,
                rejection_reason="The uploaded document contains no readable text content.",
            )

        lower = text.lower()

        # Check for carrier / vendor pitches offering services TO TrackFlow
        carrier_pitch_indicators = [
            "rapidship",
            "carrier rate",
            "carrier proposal",
            "tarifa de transporte",
            "propuesta de transportista",
            "we would love to become your preferred carrier",
            "nos gustaría ser su transportista",
            "tarifas de paquetería para trackflow",
            "carrier rates for trackflow",
            "rate card for trackflow",
        ]

        if any(ind in lower for ind in carrier_pitch_indicators):
            return ClassificationDecision(
                is_rfp=False,
                rejection_reason="Document is a carrier rate pitch or transport vendor solicitation seeking TrackFlow as a client, not an inbound customer RFP proposal.",
            )

        # Check for spam or marketing advertisements
        spam_indicators = [
            "free cruise",
            "win a free",
            "luxury caribbean holiday",
            "claim your prize",
            "viagra",
            "casino",
            "lottery",
        ]

        if any(ind in lower for ind in spam_indicators):
            return ClassificationDecision(
                is_rfp=False,
                rejection_reason="Document identified as unsolicited marketing spam or advertisement.",
            )

        # Positive customer RFP indicators: prospect requesting warehousing, fulfillment, returns
        rfp_indicators = [
            "request for proposal",
            "rfp",
            "solicitud de propuesta",
            "propuesta de servicios logísticos",
            "pliego de condiciones",
            "fulfillment",
            "almacén",
            "almacenamiento",
            "warehousing",
            "reverse logistics",
            "logística inversa",
            "devoluciones",
            "last mile",
            "última milla",
            "modaviva",
            "luna cosmetics",
        ]

        matches = sum(1 for ind in rfp_indicators if ind in lower)
        if matches >= 1:
            return ClassificationDecision(is_rfp=True, rejection_reason=None)

        # Insufficient logistics context
        return ClassificationDecision(
            is_rfp=False,
            rejection_reason="Document does not contain logistics RFP requirements or customer fulfillment specifications.",
        )
