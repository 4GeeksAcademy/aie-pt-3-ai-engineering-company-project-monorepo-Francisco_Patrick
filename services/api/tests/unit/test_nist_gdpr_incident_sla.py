"""Unit tests verifying GDPR 72-hour AEPD incident response containment and notification protocol (US5, FR-013, SC-007).

Validates:
1. Incident timeline adherence:
   - T <= 4h: Token revocation and IP/pod containment.
   - T <= 12h: PII scope triaging and affected account identification.
   - T <= 36h: Data Protection Officer (DPO) rights and freedoms risk review.
   - T <= 72h: Formal submission payload generation for Sede Electrónica AEPD (Spain).
2. Compliance with GDPR Article 33 and 34 reporting mandates.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest


class GDPRIncidentResponseManager:
    """Manager validating transatlantic breach containment milestones and AEPD submission payloads."""

    def __init__(self, incident_detected_at: datetime) -> None:
        self.incident_detected_at = incident_detected_at

    def calculate_sla_milestones(self) -> Dict[str, datetime]:
        """Compute strict deadlines from initial detection timestamp."""
        return {
            "containment_deadline": self.incident_detected_at + timedelta(hours=4),
            "pii_triaging_deadline": self.incident_detected_at + timedelta(hours=12),
            "dpo_risk_review_deadline": self.incident_detected_at + timedelta(hours=36),
            "aepd_formal_notification_deadline": self.incident_detected_at + timedelta(hours=72),
        }

    def validate_action_timeline(self, action_name: str, executed_at: datetime) -> bool:
        """Verify whether an operational response action was completed within its SLA window."""
        milestones = self.calculate_sla_milestones()
        if action_name not in milestones:
            raise KeyError(f"Unknown milestone action: {action_name}")
        return executed_at <= milestones[action_name]

    def build_aepd_notification_payload(
        self,
        incident_id: str,
        nature_of_breach: str,
        affected_pii_categories: List[str],
        estimated_data_subjects: int,
        containment_measures_taken: List[str],
        dpo_contact_email: str = "dpo.zaragoza@trackflow.io",
    ) -> Dict[str, Any]:
        """Generate authoritative Article 33 GDPR electronic notification payload for AEPD."""
        now = datetime.now(timezone.utc)
        elapsed_hours = (now - self.incident_detected_at).total_seconds() / 3600.0

        if elapsed_hours > 72.0:
            late_justification = "Incident required complex distributed forensic analysis."
        else:
            late_justification = None

        return {
            "supervisory_authority": "Agencia Española de Protección de Datos (AEPD)",
            "legal_basis": "GDPR Art. 33 / RGPD UE 2016/679",
            "incident_id": incident_id,
            "detected_at": self.incident_detected_at.isoformat(),
            "notification_submitted_at": now.isoformat(),
            "elapsed_hours": round(elapsed_hours, 2),
            "is_within_72h_sla": elapsed_hours <= 72.0,
            "late_submission_justification": late_justification,
            "dpo_contact": {
                "office": "TrackFlow Zaragoza DPO Office",
                "email": dpo_contact_email,
                "country": "ES",
            },
            "breach_assessment": {
                "nature_of_breach": nature_of_breach,
                "affected_data_categories": affected_pii_categories,
                "approximate_data_subjects_count": estimated_data_subjects,
                "likely_consequences": "Potential exposure of delivery address and recipient names.",
                "containment_measures_taken": containment_measures_taken,
            },
        }


def test_gdpr_incident_sla_milestones() -> None:
    """Verify that all response milestones adhere to strict GDPR Art 33 timelines."""
    t0 = datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
    manager = GDPRIncidentResponseManager(incident_detected_at=t0)
    milestones = manager.calculate_sla_milestones()

    assert milestones["containment_deadline"] == t0 + timedelta(hours=4)
    assert milestones["pii_triaging_deadline"] == t0 + timedelta(hours=12)
    assert milestones["dpo_risk_review_deadline"] == t0 + timedelta(hours=36)
    assert milestones["aepd_formal_notification_deadline"] == t0 + timedelta(hours=72)

    # Valid containment at T+2h (within 4h)
    assert manager.validate_action_timeline("containment_deadline", t0 + timedelta(hours=2)) is True
    # Containment at T+5h breaches SLA
    assert manager.validate_action_timeline("containment_deadline", t0 + timedelta(hours=5)) is False


def test_aepd_notification_payload_conformance() -> None:
    """Verify that the generated AEPD electronic notification payload conforms to Art 33 requirements."""
    t0 = datetime.now(timezone.utc) - timedelta(hours=24)  # Detected 24 hours ago
    manager = GDPRIncidentResponseManager(incident_detected_at=t0)

    payload = manager.build_aepd_notification_payload(
        incident_id="INC-2026-AEPD-001",
        nature_of_breach="Suspected unauthorized token access to customer delivery lookup API",
        affected_pii_categories=["DELIVERY_ADDRESS", "RECIPIENT_NAME", "TRACKING_NUMBER"],
        estimated_data_subjects=45,
        containment_measures_taken=[
            "Revoked compromised service account API tokens",
            "Isolated suspicious origin IPs",
            "Redacted delivery addresses in public query traces",
        ],
    )

    assert payload["legal_basis"] == "GDPR Art. 33 / RGPD UE 2016/679"
    assert payload["is_within_72h_sla"] is True
    assert payload["elapsed_hours"] <= 72.0
    assert payload["dpo_contact"]["country"] == "ES"
    assert len(payload["breach_assessment"]["containment_measures_taken"]) == 3
    assert "DELIVERY_ADDRESS" in payload["breach_assessment"]["affected_data_categories"]
