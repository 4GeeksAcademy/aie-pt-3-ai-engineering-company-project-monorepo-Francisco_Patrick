"""Autonomous Agent Action Policies & Human-In-The-Loop (HITL) Gate Service (FR-004, FR-007).

Enforces programmatic boundaries on high-impact irreversible actions:
1. Return Approval Threshold Gate: Returns > 100.00 EUR require human authorization.
2. In-Transit Carrier Reassignment Gate: In-transit parcels require human authorization.
3. Thread-safe operational review queue for human supervisors.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
import uuid

from domain.agent.entities import (
    AgentActionPolicy,
    AgentActionType,
    ApprovalStatus,
    AuthenticatedSessionContext,
    HumanApprovalGateRecord,
)
from presentation.schemas.security_audit import EvaluationResultSchema


class AgentActionPoliciesService:
    """Service governing autonomous agent action policies and human approval gates."""

    _instance: Optional["AgentActionPoliciesService"] = None
    _lock = threading.RLock()

    def __init__(self, max_autonomous_amount_eur: float = 100.00) -> None:
        """Initialize policies and in-memory review queue."""
        self._max_autonomous_amount_eur = max_autonomous_amount_eur
        self._queue_lock = threading.RLock()
        self._queue: Dict[str, HumanApprovalGateRecord] = {}

    @classmethod
    def get_instance(cls) -> "AgentActionPoliciesService":
        """Return singleton instance of policy service."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def evaluate_return_approval(
        self,
        session_context: Optional[AuthenticatedSessionContext],
        order_id: str,
        refund_amount_eur: float,
        shipment_status: str = "DELIVERED",
    ) -> EvaluationResultSchema:
        """Evaluate return request against monetary threshold gate.

        Args:
            session_context: Authenticated customer session.
            order_id: Target order identifier.
            refund_amount_eur: Claimed refund amount in EUR.
            shipment_status: Current delivery status of parcel.

        Returns:
            EvaluationResultSchema with autonomous decision or human review queue assignment.
        """
        # Threshold gate: > 100.00 EUR requires human operational review
        if refund_amount_eur > self._max_autonomous_amount_eur:
            req_id = f"req_hitl_{uuid.uuid4().hex[:8]}"
            session_id = session_context.session_id if session_context else "anonymous"

            record = HumanApprovalGateRecord(
                request_id=req_id,
                action_type="RETURN_APPROVAL",
                entity_id=order_id,
                requested_by_session=session_id,
                payload_snapshot={
                    "order_id": order_id,
                    "refund_amount_eur": refund_amount_eur,
                    "shipment_status": shipment_status,
                },
                requested_amount_eur=refund_amount_eur,
                status="PENDING_HUMAN_APPROVAL",
                created_at=datetime.now(timezone.utc),
            )
            with self._queue_lock:
                self._queue[req_id] = record

            return EvaluationResultSchema(
                decision="PENDING_HUMAN_APPROVAL",
                reason_code="HIGH_VALUE_RETURN_REQUIRES_HUMAN_APPROVAL",
                threshold_eur=self._max_autonomous_amount_eur,
                human_review_queue_id=req_id,
            )

        return EvaluationResultSchema(
            decision="AUTONOMOUSLY_APPROVED",
            reason_code="RETURN_WITHIN_AUTONOMOUS_LIMITS",
            threshold_eur=self._max_autonomous_amount_eur,
        )

    def evaluate_carrier_reassignment(
        self,
        session_context: Optional[AuthenticatedSessionContext],
        order_id: str,
        target_carrier: str,
        shipment_status: str,
    ) -> EvaluationResultSchema:
        """Evaluate carrier switch against in-transit parcel protection policy.

        Args:
            session_context: Authenticated customer session.
            order_id: Target order identifier.
            target_carrier: Destination carrier name.
            shipment_status: Current delivery status.

        Returns:
            EvaluationResultSchema with decision and reason code.
        """
        normalized_status = (shipment_status or "").strip().upper()
        if normalized_status in ("IN_TRANSIT", "OUT_FOR_DELIVERY"):
            req_id = f"req_hitl_{uuid.uuid4().hex[:8]}"
            session_id = session_context.session_id if session_context else "anonymous"

            record = HumanApprovalGateRecord(
                request_id=req_id,
                action_type="CARRIER_REASSIGNMENT",
                entity_id=order_id,
                requested_by_session=session_id,
                payload_snapshot={
                    "order_id": order_id,
                    "target_carrier": target_carrier,
                    "shipment_status": shipment_status,
                },
                requested_amount_eur=0.0,
                status="PENDING_HUMAN_APPROVAL",
                created_at=datetime.now(timezone.utc),
            )
            with self._queue_lock:
                self._queue[req_id] = record

            return EvaluationResultSchema(
                decision="PENDING_HUMAN_APPROVAL",
                reason_code="IN_TRANSIT_CARRIER_CHANGE_REQUIRES_HUMAN_APPROVAL",
                human_review_queue_id=req_id,
            )

        return EvaluationResultSchema(
            decision="AUTONOMOUSLY_APPROVED",
            reason_code="CARRIER_REASSIGNMENT_PERMITTED_BEFORE_DISPATCH",
        )

    def list_pending_reviews(self, limit: int = 50) -> List[HumanApprovalGateRecord]:
        """List requests pending operational review."""
        with self._queue_lock:
            pending = [r for r in self._queue.values() if r.status == "PENDING_HUMAN_APPROVAL"]
            return pending[:limit]

    def get_review_request(self, request_id: str) -> Optional[HumanApprovalGateRecord]:
        """Retrieve a specific review request by ID."""
        with self._queue_lock:
            return self._queue.get(request_id)

    def review_pending_request(
        self,
        request_id: str,
        reviewer_id: str,
        approved: bool,
        decision_notes: Optional[str] = None,
    ) -> HumanApprovalGateRecord:
        """Apply operational reviewer decision to a queued action."""
        with self._queue_lock:
            record = self._queue.get(request_id)
            if not record:
                raise KeyError(f"Review request '{request_id}' not found.")

            new_status: ApprovalStatus = "HUMAN_APPROVED" if approved else "HUMAN_REJECTED"
            updated = HumanApprovalGateRecord(
                request_id=record.request_id,
                action_type=record.action_type,
                entity_id=record.entity_id,
                requested_by_session=record.requested_by_session,
                payload_snapshot=record.payload_snapshot,
                requested_amount_eur=record.requested_amount_eur,
                status=new_status,
                reviewer_id=reviewer_id,
                decision_notes=decision_notes,
                created_at=record.created_at,
                reviewed_at=datetime.now(timezone.utc),
            )
            self._queue[request_id] = updated
            return updated


def get_agent_action_policies_service() -> AgentActionPoliciesService:
    """FastAPI dependency provider for AgentActionPoliciesService."""
    return AgentActionPoliciesService.get_instance()
