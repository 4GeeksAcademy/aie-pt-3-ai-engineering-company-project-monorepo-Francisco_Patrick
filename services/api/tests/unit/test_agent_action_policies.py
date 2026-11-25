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
