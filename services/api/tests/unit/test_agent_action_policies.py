"""Unit test verifying return approval threshold gate and in-transit carrier reassignment refusal."""

import pytest
from application.services.agent_action_policies import AgentActionPoliciesService
from domain.agent.entities import AuthenticatedSessionContext


@pytest.fixture
def policy_service() -> AgentActionPoliciesService:
    """Create a fresh AgentActionPoliciesService instance."""
    return AgentActionPoliciesService()


@pytest.fixture
def auth_session() -> AuthenticatedSessionContext:
    """Standard authenticated session owning order 10492."""
    return AuthenticatedSessionContext(
        session_id="sess_test_01",
        customer_id="cust_test_01",
        customer_segment="B2C",
        primary_operating_country="ES",
        authorized_order_ids=("10492",),
    )


def test_return_approval_autonomous_under_threshold(
    policy_service: AgentActionPoliciesService,
    auth_session: AuthenticatedSessionContext,
) -> None:
    """Verify returns under or equal to 100 EUR are approved autonomously."""
    decision = policy_service.evaluate_return_approval(
        session_context=auth_session,
        order_id="10492",
        refund_amount_eur=75.50,
        shipment_status="DELIVERED",
    )
    assert decision.decision == "AUTONOMOUSLY_APPROVED"
    assert decision.threshold_eur == 100.0


def test_return_approval_threshold_gate_exceeding_100_eur(
    policy_service: AgentActionPoliciesService,
    auth_session: AuthenticatedSessionContext,
) -> None:
    """Verify returns exceeding 100 EUR transition to PENDING_HUMAN_APPROVAL."""
    decision = policy_service.evaluate_return_approval(
        session_context=auth_session,
        order_id="10492",
        refund_amount_eur=150.00,
        shipment_status="DELIVERED",
    )
    assert decision.decision == "PENDING_HUMAN_APPROVAL"
    assert decision.reason_code == "HIGH_VALUE_RETURN_REQUIRES_HUMAN_APPROVAL"
    assert decision.human_review_queue_id is not None

    # Verify queued in pending
    pending = policy_service.list_pending_reviews()
    assert any(r.request_id == decision.human_review_queue_id for r in pending)


def test_in_transit_carrier_reassignment_gate(
    policy_service: AgentActionPoliciesService,
    auth_session: AuthenticatedSessionContext,
) -> None:
    """Verify parcel carrier reassignment on in-transit parcel requires human approval."""
    decision = policy_service.evaluate_carrier_reassignment(
        session_context=auth_session,
        order_id="10492",
        target_carrier="DHL",
        shipment_status="IN_TRANSIT",
    )
    assert decision.decision == "PENDING_HUMAN_APPROVAL"
    assert decision.reason_code == "IN_TRANSIT_CARRIER_CHANGE_REQUIRES_HUMAN_APPROVAL"
    assert decision.human_review_queue_id is not None


def test_human_approval_lifecycle(
    policy_service: AgentActionPoliciesService,
    auth_session: AuthenticatedSessionContext,
) -> None:
    """Verify operational reviewer can approve or reject a queued action."""
    decision = policy_service.evaluate_return_approval(
        session_context=auth_session,
        order_id="10492",
        refund_amount_eur=250.00,
        shipment_status="DELIVERED",
    )
    queue_id = decision.human_review_queue_id
    assert queue_id is not None

    # Review request with approval
    reviewed = policy_service.review_pending_request(
        request_id=queue_id,
        reviewer_id="ops_lead_01",
        approved=True,
        decision_notes="Customer VIP receipt verified manually",
    )
    assert reviewed.status == "HUMAN_APPROVED"
    assert reviewed.reviewer_id == "ops_lead_01"
    assert reviewed.reviewed_at is not None


def test_high_value_dispatch_gate(
    policy_service: AgentActionPoliciesService,
    auth_session: AuthenticatedSessionContext,
) -> None:
    """Verify high-value dispatch (> 500 EUR) or unverified address requires human approval (US4, FR-012)."""
    # 1. Under threshold with verified address -> autonomous
    res_under = policy_service.evaluate_high_value_dispatch(
        session_context=auth_session,
        parcel_id="PCL-101",
        declared_value_eur=350.00,
        address_verified=True,
    )
    assert res_under.decision == "AUTONOMOUSLY_APPROVED"

    # 2. Exceeding 500 EUR -> PENDING_HUMAN_APPROVAL
    res_over = policy_service.evaluate_high_value_dispatch(
        session_context=auth_session,
        parcel_id="PCL-102",
        declared_value_eur=750.00,
        address_verified=True,
    )
    assert res_over.decision == "PENDING_HUMAN_APPROVAL"
    assert res_over.reason_code == "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL"
    assert res_over.human_review_queue_id is not None

    # 3. Unverified address under 500 EUR -> PENDING_HUMAN_APPROVAL
    res_unverified = policy_service.evaluate_high_value_dispatch(
        session_context=auth_session,
        parcel_id="PCL-103",
        declared_value_eur=200.00,
        address_verified=False,
    )
    assert res_unverified.decision == "PENDING_HUMAN_APPROVAL"


def test_cross_brand_metric_sharing_gate(
    policy_service: AgentActionPoliciesService,
) -> None:
    """Verify that cross-brand metric queries between tenants are blocked with access denied (US4, FR-012)."""
    from domain.agent.entities import AuthenticatedSessionContext

    # Session for Brand Zara
    brand_a_session = AuthenticatedSessionContext(
        session_id="sess_brand_a",
        customer_id="cust_brand_a",
        customer_segment="B2B",
        primary_operating_country="ES",
        authorized_order_ids=("ORD-1",),
        brand_id="brand_zara",
    )

    # 1. Attempting to query Brand Mango -> Blocked
    res_cross = policy_service.evaluate_cross_brand_metric_share(
        session_context=brand_a_session,
        target_brand_id="brand_mango",
        metric_name="on_time_delivery_rate",
    )
    assert res_cross.decision == "BLOCKED_SECURITY_VIOLATION"
    assert res_cross.reason_code == "CROSS_BRAND_METRIC_ACCESS_DENIED"

    # 2. Querying own brand metrics -> Allowed
    res_own = policy_service.evaluate_cross_brand_metric_share(
        session_context=brand_a_session,
        target_brand_id="brand_zara",
        metric_name="on_time_delivery_rate",
    )
    assert res_own.decision == "AUTONOMOUSLY_APPROVED"
    assert res_own.reason_code == "BRAND_METRIC_ACCESS_PERMITTED"


def test_fail_secure_timeout_handling() -> None:
    """Verify that timed-out approval requests transition to EXPIRED_FAIL_SECURE and reject late reviews (US4, T032)."""
    from datetime import datetime, timedelta, timezone

    # Create service with negative timeout so it is immediately expired
    policy_svc = AgentActionPoliciesService(timeout_minutes=-1)
    auth_session = AuthenticatedSessionContext(
        session_id="sess_timeout_test",
        customer_id="cust_01",
        authorized_order_ids=("ORD-123",),
    )

    decision = policy_svc.evaluate_return_approval(
        session_context=auth_session,
        order_id="ORD-123",
        refund_amount_eur=300.00,
    )
    req_id = decision.human_review_queue_id
    assert req_id is not None

    # Check expiration triggers
    expired_count = policy_svc.check_expirations()
    assert expired_count >= 1

    record = policy_svc.get_review_request(req_id)
    assert record is not None
    assert record.status == "EXPIRED_FAIL_SECURE"

    # Attempting to approve an expired request must fail securely
    with pytest.raises(ValueError, match="expired and failed secure"):
        policy_svc.review_pending_request(
            request_id=req_id,
            reviewer_id="late_supervisor",
            approved=True,
        )

