"""Autonomous Agent Action Policies & Human-In-The-Loop (HITL) Gate Service (FR-004, FR-007).

Enforces programmatic boundaries on high-impact irreversible actions:
1. Return Approval Threshold Gate: Returns > 100.00 EUR require human authorization.
2. In-Transit Carrier Reassignment Gate: In-transit parcels require human authorization.
3. Thread-safe operational review queue for human supervisors.
"""

from datetime import datetime, timedelta, timezone
import threading
from typing import Any, Dict, List, Optional
import uuid

from application.services.guardrail_observability import sanitize_audit_preview
from domain.agent.entities import (
    AgentActionPolicy,
    AgentActionType,
    ApprovalStatus,
    AuthenticatedSessionContext,
    HumanApprovalGateRecord,
    SecurityAuditLogEntry,
)
from domain.agent.ports import GuardrailObservabilityPort
from presentation.schemas.security_audit import EvaluationResultSchema


class AgentActionPoliciesService:
    """Service governing autonomous agent action policies and human approval gates."""

    _instance: Optional["AgentActionPoliciesService"] = None
    _lock = threading.RLock()

    def __init__(
        self,
        max_autonomous_amount_eur: float = 100.00,
        high_value_dispatch_threshold_eur: float = 500.00,
        timeout_minutes: int = 60,
        observability: Optional[GuardrailObservabilityPort] = None,
    ) -> None:
        """Initialize policies and in-memory review queue."""
        self._max_autonomous_amount_eur = max_autonomous_amount_eur
        self._high_value_dispatch_threshold_eur = high_value_dispatch_threshold_eur
        self._timeout_minutes = timeout_minutes
        self._observability = observability
        self._queue_lock = threading.RLock()
        self._queue: Dict[str, HumanApprovalGateRecord] = {}

    @property
    def observability(self) -> GuardrailObservabilityPort:
        """Return configured or shared GuardrailObservabilityPort instance."""
        if self._observability is not None:
            return self._observability
        from presentation.dependencies import get_guardrail_observability_dep

        return get_guardrail_observability_dep()

    def _emit_audit_log(
        self,
        session_context: Optional[AuthenticatedSessionContext],
        event_category: str,
        action_attempted: str,
        input_parameters: Dict[str, Any],
        policy_rules_evaluated: List[str],
        decision_outcome: str,
        reasoning_rationale: str,
        session_id_override: Optional[str] = None,
    ) -> SecurityAuditLogEntry:
        """Create and record a sanitized SecurityAuditLogEntry in GuardrailObservabilityService (FR-011, AC-8)."""
        session_id = (
            session_id_override
            or (session_context.session_id if session_context else None)
            or "anonymous"
        )
        tenant_id = (
            (getattr(session_context, "brand_id", None) if session_context else None)
            or (session_context.customer_id if session_context else None)
            or "default"
        )
        redacted_params: Dict[str, Any] = {}
        for key, value in input_parameters.items():
            if isinstance(value, str):
                redacted_params[key] = sanitize_audit_preview(value)
            else:
                redacted_params[key] = value

        entry = SecurityAuditLogEntry(
            event_id=f"aud_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc),
            agent_id="TF-AI-01-SUPPORT-AGENT",
            session_id=session_id,
            tenant_id=str(tenant_id),
            event_category=event_category,
            action_attempted=action_attempted,
            input_parameters_redacted=redacted_params,
            policy_rules_evaluated=list(policy_rules_evaluated),
            decision_outcome=decision_outcome,
            reasoning_rationale=sanitize_audit_preview(reasoning_rationale),
        )
        self.observability.record_security_audit_log(entry)
        return entry

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
            now = datetime.now(timezone.utc)

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
                created_at=now,
                expires_at=now + timedelta(minutes=self._timeout_minutes),
            )
            with self._queue_lock:
                self._queue[req_id] = record

            result = EvaluationResultSchema(
                decision="PENDING_HUMAN_APPROVAL",
                reason_code="HIGH_VALUE_RETURN_REQUIRES_HUMAN_APPROVAL",
                threshold_eur=self._max_autonomous_amount_eur,
                human_review_queue_id=req_id,
            )
            self._emit_audit_log(
                session_context=session_context,
                event_category="HITL_POLICY_EVALUATION",
                action_attempted="RETURN_APPROVAL",
                input_parameters={
                    "order_id": order_id,
                    "refund_amount_eur": refund_amount_eur,
                    "shipment_status": shipment_status,
                    "human_review_queue_id": req_id,
                },
                policy_rules_evaluated=["RETURN_APPROVAL_THRESHOLD_100_EUR"],
                decision_outcome=result.decision,
                reasoning_rationale=result.reason_code or "HIGH_VALUE_RETURN_REQUIRES_HUMAN_APPROVAL",
            )
            return result

        result = EvaluationResultSchema(
            decision="AUTONOMOUSLY_APPROVED",
            reason_code="RETURN_WITHIN_AUTONOMOUS_LIMITS",
            threshold_eur=self._max_autonomous_amount_eur,
        )
        self._emit_audit_log(
            session_context=session_context,
            event_category="HITL_POLICY_EVALUATION",
            action_attempted="RETURN_APPROVAL",
            input_parameters={
                "order_id": order_id,
                "refund_amount_eur": refund_amount_eur,
                "shipment_status": shipment_status,
            },
            policy_rules_evaluated=["RETURN_APPROVAL_THRESHOLD_100_EUR"],
            decision_outcome=result.decision,
            reasoning_rationale=result.reason_code or "RETURN_WITHIN_AUTONOMOUS_LIMITS",
        )
        return result

    def evaluate_high_value_dispatch(
        self,
        session_context: Optional[AuthenticatedSessionContext],
        parcel_id: str,
        declared_value_eur: float,
        address_verified: bool = True,
    ) -> EvaluationResultSchema:
        """Evaluate high-value or unverified parcel dispatch against supervisor gate."""
        if declared_value_eur > self._high_value_dispatch_threshold_eur or not address_verified:
            req_id = f"req_hitl_{uuid.uuid4().hex[:8]}"
            session_id = session_context.session_id if session_context else "anonymous"
            now = datetime.now(timezone.utc)

            record = HumanApprovalGateRecord(
                request_id=req_id,
                action_type="HIGH_VALUE_DISPATCH",
                entity_id=parcel_id,
                requested_by_session=session_id,
                payload_snapshot={
                    "parcel_id": parcel_id,
                    "declared_value_eur": declared_value_eur,
                    "address_verified": address_verified,
                },
                requested_amount_eur=declared_value_eur,
                status="PENDING_HUMAN_APPROVAL",
                created_at=now,
                expires_at=now + timedelta(minutes=self._timeout_minutes),
            )
            with self._queue_lock:
                self._queue[req_id] = record

            result = EvaluationResultSchema(
                decision="PENDING_HUMAN_APPROVAL",
                reason_code="HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL",
                threshold_eur=self._high_value_dispatch_threshold_eur,
                human_review_queue_id=req_id,
            )
            self._emit_audit_log(
                session_context=session_context,
                event_category="HITL_POLICY_EVALUATION",
                action_attempted="HIGH_VALUE_DISPATCH",
                input_parameters={
                    "parcel_id": parcel_id,
                    "declared_value_eur": declared_value_eur,
                    "address_verified": address_verified,
                    "human_review_queue_id": req_id,
                },
                policy_rules_evaluated=[
                    "HIGH_VALUE_DISPATCH_THRESHOLD_500_EUR",
                    "ADDRESS_VERIFICATION_GATE",
                ],
                decision_outcome=result.decision,
                reasoning_rationale=result.reason_code or "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL",
            )
            return result

        result = EvaluationResultSchema(
            decision="AUTONOMOUSLY_APPROVED",
            reason_code="DISPATCH_WITHIN_AUTONOMOUS_LIMITS",
            threshold_eur=self._high_value_dispatch_threshold_eur,
        )
        self._emit_audit_log(
            session_context=session_context,
            event_category="HITL_POLICY_EVALUATION",
            action_attempted="HIGH_VALUE_DISPATCH",
            input_parameters={
                "parcel_id": parcel_id,
                "declared_value_eur": declared_value_eur,
                "address_verified": address_verified,
            },
            policy_rules_evaluated=[
                "HIGH_VALUE_DISPATCH_THRESHOLD_500_EUR",
                "ADDRESS_VERIFICATION_GATE",
            ],
            decision_outcome=result.decision,
            reasoning_rationale=result.reason_code or "DISPATCH_WITHIN_AUTONOMOUS_LIMITS",
        )
        return result

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
            now = datetime.now(timezone.utc)

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
                created_at=now,
                expires_at=now + timedelta(minutes=self._timeout_minutes),
            )
            with self._queue_lock:
                self._queue[req_id] = record

            result = EvaluationResultSchema(
                decision="PENDING_HUMAN_APPROVAL",
                reason_code="IN_TRANSIT_CARRIER_CHANGE_REQUIRES_HUMAN_APPROVAL",
                human_review_queue_id=req_id,
            )
            self._emit_audit_log(
                session_context=session_context,
                event_category="HITL_POLICY_EVALUATION",
                action_attempted="CARRIER_REASSIGNMENT",
                input_parameters={
                    "order_id": order_id,
                    "target_carrier": target_carrier,
                    "shipment_status": shipment_status,
                    "human_review_queue_id": req_id,
                },
                policy_rules_evaluated=["IN_TRANSIT_CARRIER_REASSIGNMENT_GATE"],
                decision_outcome=result.decision,
                reasoning_rationale=result.reason_code or "IN_TRANSIT_CARRIER_CHANGE_REQUIRES_HUMAN_APPROVAL",
            )
            return result

        result = EvaluationResultSchema(
            decision="AUTONOMOUSLY_APPROVED",
            reason_code="CARRIER_REASSIGNMENT_PERMITTED_BEFORE_DISPATCH",
        )
        self._emit_audit_log(
            session_context=session_context,
            event_category="HITL_POLICY_EVALUATION",
            action_attempted="CARRIER_REASSIGNMENT",
            input_parameters={
                "order_id": order_id,
                "target_carrier": target_carrier,
                "shipment_status": shipment_status,
            },
            policy_rules_evaluated=["IN_TRANSIT_CARRIER_REASSIGNMENT_GATE"],
            decision_outcome=result.decision,
            reasoning_rationale=result.reason_code or "CARRIER_REASSIGNMENT_PERMITTED_BEFORE_DISPATCH",
        )
        return result

    def evaluate_cross_brand_metric_share(
        self,
        session_context: Optional[AuthenticatedSessionContext],
        target_brand_id: str,
        metric_name: str,
    ) -> EvaluationResultSchema:
        """Evaluate B2B metric request to prevent cross-tenant information disclosure."""
        session_brand = getattr(session_context, "brand_id", None) if session_context else None
        if not session_brand or session_brand != target_brand_id:
            result = EvaluationResultSchema(
                decision="BLOCKED_SECURITY_VIOLATION",
                reason_code="CROSS_BRAND_METRIC_ACCESS_DENIED",
            )
            self._emit_audit_log(
                session_context=session_context,
                event_category="HITL_POLICY_EVALUATION",
                action_attempted="CROSS_BRAND_METRIC_SHARE",
                input_parameters={
                    "session_brand_id": session_brand or "none",
                    "target_brand_id": target_brand_id,
                    "metric_name": metric_name,
                },
                policy_rules_evaluated=["CROSS_BRAND_TENANT_ISOLATION_GATE"],
                decision_outcome=result.decision,
                reasoning_rationale=result.reason_code or "CROSS_BRAND_METRIC_ACCESS_DENIED",
            )
            return result

        result = EvaluationResultSchema(
            decision="AUTONOMOUSLY_APPROVED",
            reason_code="BRAND_METRIC_ACCESS_PERMITTED",
        )
        self._emit_audit_log(
            session_context=session_context,
            event_category="HITL_POLICY_EVALUATION",
            action_attempted="CROSS_BRAND_METRIC_SHARE",
            input_parameters={
                "session_brand_id": session_brand,
                "target_brand_id": target_brand_id,
                "metric_name": metric_name,
            },
            policy_rules_evaluated=["CROSS_BRAND_TENANT_ISOLATION_GATE"],
            decision_outcome=result.decision,
            reasoning_rationale=result.reason_code or "BRAND_METRIC_ACCESS_PERMITTED",
        )
        return result

    def check_expirations(self) -> int:
        """Scan active review queue and transition timed-out requests to EXPIRED_FAIL_SECURE."""
        now = datetime.now(timezone.utc)
        expired_count = 0
        with self._queue_lock:
            for req_id, record in list(self._queue.items()):
                if record.status == "PENDING_HUMAN_APPROVAL" and record.expires_at and now > record.expires_at:
                    updated = HumanApprovalGateRecord(
                        request_id=record.request_id,
                        action_type=record.action_type,
                        entity_id=record.entity_id,
                        requested_by_session=record.requested_by_session,
                        payload_snapshot=record.payload_snapshot,
                        requested_amount_eur=record.requested_amount_eur,
                        status="EXPIRED_FAIL_SECURE",
                        reviewer_id="system_fail_secure_timeout",
                        decision_notes="Review window expired before human confirmation.",
                        created_at=record.created_at,
                        reviewed_at=now,
                        expires_at=record.expires_at,
                    )
                    self._queue[req_id] = updated
                    expired_count += 1
                    self._emit_audit_log(
                        session_context=None,
                        session_id_override=record.requested_by_session,
                        event_category="HITL_FAIL_SECURE_TIMEOUT",
                        action_attempted=record.action_type,
                        input_parameters={
                            "request_id": record.request_id,
                            "entity_id": record.entity_id,
                            "requested_amount_eur": record.requested_amount_eur,
                        },
                        policy_rules_evaluated=["HITL_EXPIRATION_FAIL_SECURE_GATE"],
                        decision_outcome="EXPIRED_FAIL_SECURE",
                        reasoning_rationale="Review window expired before human confirmation.",
                    )
        return expired_count

    def list_pending_reviews(self, limit: int = 50) -> List[HumanApprovalGateRecord]:
        """List requests pending operational review (running expiration checks first)."""
        self.check_expirations()
        with self._queue_lock:
            pending = [r for r in self._queue.values() if r.status == "PENDING_HUMAN_APPROVAL"]
            return pending[:limit]

    def get_review_request(self, request_id: str) -> Optional[HumanApprovalGateRecord]:
        """Retrieve a specific review request by ID."""
        self.check_expirations()
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
        self.check_expirations()
        with self._queue_lock:
            record = self._queue.get(request_id)
            if not record:
                raise KeyError(f"Review request '{request_id}' not found.")

            if record.status == "EXPIRED_FAIL_SECURE":
                raise ValueError(f"Review request '{request_id}' has expired and failed secure.")

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
                expires_at=record.expires_at,
            )
            self._queue[request_id] = updated
            self._emit_audit_log(
                session_context=None,
                session_id_override=record.requested_by_session,
                event_category="HITL_SUPERVISOR_REVIEW",
                action_attempted=record.action_type,
                input_parameters={
                    "request_id": record.request_id,
                    "entity_id": record.entity_id,
                    "reviewer_id": reviewer_id,
                    "approved": approved,
                },
                policy_rules_evaluated=["HITL_SUPERVISOR_AUTHORIZATION_GATE"],
                decision_outcome=new_status,
                reasoning_rationale=decision_notes or f"Supervisor {reviewer_id} resolved request as {new_status}",
            )
            return updated


def get_agent_action_policies_service() -> AgentActionPoliciesService:
    """FastAPI dependency provider for AgentActionPoliciesService."""
    return AgentActionPoliciesService.get_instance()
