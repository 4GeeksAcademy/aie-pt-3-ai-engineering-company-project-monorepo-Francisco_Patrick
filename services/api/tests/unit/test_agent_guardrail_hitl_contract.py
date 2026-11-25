"""Contract test for agent guardrail HITL payload validation.

Validates payload conformance against contracts/agent-guardrail-hitl.schema.json,
Pydantic model AgentGuardrailHITLPayload, and secures review endpoints against
unauthenticated access, unauthorized roles, and reviewer_id spoofing.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from application.services.agent_action_policies import (
    AgentActionPoliciesService,
    get_agent_action_policies_service,
)
from domain.agent.entities import AuthenticatedSessionContext
from domain.models import User
from presentation.api.v1.agent import router as agent_router
from presentation.dependencies import get_current_user
from presentation.schemas.security_audit import (
    ActionParametersSchema,
    AgentGuardrailHITLPayload,
    EvaluationResultSchema,
    SessionContextSchema,
)


def test_agent_guardrail_hitl_contract_validation() -> None:
    """Validate that high-value return action payload conforms to contract schema."""
    raw_payload = {
        "action_type": "RETURN_APPROVAL",
        "session_context": {
            "customer_id": "cust_es_01",
            "authenticated_orders": ["10492", "88310"],
            "brand_id": "brand_zara_es",
            "country": "ES",
        },
        "parameters": {
            "entity_id": "10492",
            "refund_amount_eur": 149.99,
            "shipment_status": "DELIVERED",
            "return_reason": "Defective item",
        },
        "evaluation_result": {
            "decision": "PENDING_HUMAN_APPROVAL",
            "reason_code": "HIGH_VALUE_RETURN_REQUIRES_HUMAN_APPROVAL",
            "threshold_eur": 100.0,
            "human_review_queue_id": "req_hitl_9921",
        },
    }

    validated = AgentGuardrailHITLPayload.model_validate(raw_payload)
    assert validated.action_type == "RETURN_APPROVAL"
    assert validated.parameters.refund_amount_eur == 149.99
    assert validated.evaluation_result is not None
    assert validated.evaluation_result.decision == "PENDING_HUMAN_APPROVAL"


@pytest.fixture
def hitl_test_app():
    """Create a test FastAPI application with isolated action review state."""
    app = FastAPI()
    app.include_router(agent_router, prefix="/api/v1/agent")
    policy_svc = AgentActionPoliciesService(max_autonomous_amount_eur=100.0)
    app.dependency_overrides[get_agent_action_policies_service] = lambda: policy_svc
    return app, policy_svc


def test_actions_review_endpoints_require_authentication(hitl_test_app) -> None:
    """Unauthenticated calls to /actions/review return HTTP 401 Unauthorized."""
    app, _ = hitl_test_app
    client = TestClient(app)

    # 1. GET /actions/review without auth
    resp_get = client.get("/api/v1/agent/actions/review")
    assert resp_get.status_code == 401

    # 2. POST /actions/review/{request_id} without auth
    resp_post = client.post(
        "/api/v1/agent/actions/review/req_123",
        json={"approved": True, "decision_notes": "Attempt without token"},
    )
    assert resp_post.status_code == 401


def test_actions_review_endpoints_reject_non_supervisor_roles(hitl_test_app) -> None:
    """Authenticated users with role 'user' are rejected with HTTP 403 Forbidden."""
    app, _ = hitl_test_app
    regular_user = User(
        id="usr_regular_01",
        email="standard.user@trackflow.io",
        hashed_password="hashed_pw",
        role="user",
        created_at="2026-01-01T00:00:00Z",
    )
    app.dependency_overrides[get_current_user] = lambda: regular_user
    client = TestClient(app)

    resp_get = client.get("/api/v1/agent/actions/review")
    assert resp_get.status_code == 403
    assert "Supervisor or administrator role required" in resp_get.json()["detail"]

    resp_post = client.post(
        "/api/v1/agent/actions/review/req_123",
        json={"approved": True, "decision_notes": "Unauthorized attempt"},
    )
    assert resp_post.status_code == 403
    assert "Supervisor or administrator role required" in resp_post.json()["detail"]


def test_actions_review_endpoints_supervisor_decision_and_anti_spoofing(hitl_test_app) -> None:
    """Supervisor can list reviews and approve actions; reviewer_id cannot be spoofed by client."""
    app, policy_svc = hitl_test_app
    supervisor_user = User(
        id="sup_user_01",
        email="supervisor.ops@trackflow.io",
        hashed_password="hashed_pw",
        role="manager",
        created_at="2026-01-01T00:00:00Z",
    )
    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    client = TestClient(app)

    # Enqueue a high-value return requiring review
    session_ctx = AuthenticatedSessionContext(
        session_id="sess_client_99",
        customer_id="cust_es_01",
        customer_segment="B2C",
        primary_operating_country="ES",
        authorized_order_ids=("ORD-9910",),
    )
    eval_result = policy_svc.evaluate_return_approval(
        session_context=session_ctx,
        order_id="ORD-9910",
        refund_amount_eur=250.00,
        shipment_status="DELIVERED",
    )
    req_id = eval_result.human_review_queue_id
    assert req_id is not None

    # List pending reviews
    resp_list = client.get("/api/v1/agent/actions/review")
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 1
    assert items[0]["request_id"] == req_id
    assert items[0]["status"] == "PENDING_HUMAN_APPROVAL"

    # Submit review decision attempting to spoof reviewer_id as 'attacker@external.com'
    resp_approve = client.post(
        f"/api/v1/agent/actions/review/{req_id}",
        json={
            "reviewer_id": "attacker@external.com",
            "approved": True,
            "decision_notes": "Approved by operational supervisor after inspection.",
        },
    )
    assert resp_approve.status_code == 200
    approved_record = resp_approve.json()
    assert approved_record["status"] == "HUMAN_APPROVED"
    # Verify reviewer_id was forced to authenticated user's email, preventing spoofing
    assert approved_record["reviewer_id"] == "supervisor.ops@trackflow.io"
    assert approved_record["decision_notes"] == "Approved by operational supervisor after inspection."


def test_nist_governance_actions_review_post_endpoint(hitl_test_app) -> None:
    """Verify POST /api/v1/agent/actions/review conforms to contracts/nist-governance-api.openapi.json."""
    app, policy_svc = hitl_test_app
    supervisor_user = User(
        id="sup_user_02",
        email="lead.ops@trackflow.io",
        hashed_password="hashed_pw",
        role="admin",
        created_at="2026-01-01T00:00:00Z",
    )
    app.dependency_overrides[get_current_user] = lambda: supervisor_user
    client = TestClient(app)

    session_ctx = AuthenticatedSessionContext(
        session_id="sess_nist_01",
        customer_id="cust_es_02",
        authorized_order_ids=("ORD-5501",),
    )
    eval_result = policy_svc.evaluate_return_approval(
        session_context=session_ctx,
        order_id="ORD-5501",
        refund_amount_eur=180.00,
        shipment_status="DELIVERED",
    )
    req_id = eval_result.human_review_queue_id
    assert req_id is not None

    # Submit decision via POST /api/v1/agent/actions/review
    resp = client.post(
        "/api/v1/agent/actions/review",
        json={
            "request_id": req_id,
            "decision": "APPROVE",
            "reviewer_id": "lead.ops@trackflow.io",
            "decision_notes": "NIST CSF review authorized by admin lead.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == req_id
    assert data["status"] == "HUMAN_APPROVED"
    assert data["reviewer_id"] == "lead.ops@trackflow.io"


