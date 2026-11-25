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
from application.services.guardrail_observability import GuardrailObservabilityService
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
    obs_svc = GuardrailObservabilityService()
    policy_svc = AgentActionPoliciesService(
        max_autonomous_amount_eur=100.0,
        observability=obs_svc,
    )
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

    # Submit decision via POST /api/v1/agent/actions/review with spoofed reviewer_id
    resp = client.post(
        "/api/v1/agent/actions/review",
        json={
            "request_id": req_id,
            "decision": "APPROVE",
            "reviewer_id": "spoofed.attacker@external.com",
            "decision_notes": "NIST CSF review authorized by admin lead.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == req_id
    assert data["status"] == "HUMAN_APPROVED"
    # Anti-spoofing: reviewer_id is resolved from authenticated JWT user
    assert data["reviewer_id"] == "lead.ops@trackflow.io"

    # Also verify omitting optional reviewer_id succeeds and resolves from JWT
    eval_result_2 = policy_svc.evaluate_return_approval(
        session_context=session_ctx,
        order_id="ORD-5501",
        refund_amount_eur=210.00,
        shipment_status="DELIVERED",
    )
    req_id_2 = eval_result_2.human_review_queue_id
    assert req_id_2 is not None

    resp_no_reviewer = client.post(
        "/api/v1/agent/actions/review",
        json={
            "request_id": req_id_2,
            "decision": "REJECT",
            "decision_notes": "Rejected without redundant reviewer_id in payload.",
        },
    )
    assert resp_no_reviewer.status_code == 200
    data_2 = resp_no_reviewer.json()
    assert data_2["request_id"] == req_id_2
    assert data_2["status"] == "HUMAN_REJECTED"
    assert data_2["reviewer_id"] == "lead.ops@trackflow.io"

    # Confirm SecurityAuditLogEntry records were emitted for both evaluations and reviews
    audit_logs = policy_svc.observability.list_security_audit_logs(
        session_id="sess_nist_01"
    )
    assert len(audit_logs) == 4
    assert [log.decision_outcome for log in audit_logs] == [
        "PENDING_HUMAN_APPROVAL",
        "HUMAN_APPROVED",
        "PENDING_HUMAN_APPROVAL",
        "HUMAN_REJECTED",
    ]


def test_high_value_dispatch_contract_and_endpoint_hitl_gate(hitl_test_app) -> None:
    """Verify HIGH_VALUE_DISPATCH contract payload and POST /api/v1/agent/actions/dispatch runtime HITL gate."""
    raw_payload = {
        "action_type": "HIGH_VALUE_DISPATCH",
        "session_context": {
            "customer_id": "cust_es_01",
            "authenticated_orders": ["10492"],
            "brand_id": "brand_zara_es",
            "country": "ES",
        },
        "parameters": {
            "entity_id": "PKG-9901",
            "parcel_id": "PKG-9901",
            "declared_value_eur": 850.0,
            "address_verified": True,
        },
        "evaluation_result": {
            "decision": "PENDING_HUMAN_APPROVAL",
            "reason_code": "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL",
            "threshold_eur": 500.0,
            "human_review_queue_id": "req_hitl_8812",
        },
    }
    validated = AgentGuardrailHITLPayload.model_validate(raw_payload)
    assert validated.action_type == "HIGH_VALUE_DISPATCH"
    assert validated.parameters.declared_value_eur == 850.0

    app, _ = hitl_test_app
    operator_user = User(
        id="usr_ops_01",
        email="ops.agent@trackflow.io",
        hashed_password="hashed_pw",
        role="manager",
        created_at="2026-01-01T00:00:00Z",
    )
    app.dependency_overrides[get_current_user] = lambda: operator_user
    client = TestClient(app)

    # 1. Dispatch > 500 EUR transitions to PENDING_HUMAN_APPROVAL and enters review queue
    resp_high = client.post(
        "/api/v1/agent/actions/dispatch",
        json={
            "parcel_id": "PKG-HV-777",
            "declared_value_eur": 680.0,
            "address_verified": True,
            "order_id": "ORD-777",
        },
    )
    assert resp_high.status_code == 200
    high_data = resp_high.json()
    assert high_data["decision"] == "PENDING_HUMAN_APPROVAL"
    assert high_data["reason_code"] == "HIGH_VALUE_DISPATCH_REQUIRES_HUMAN_APPROVAL"
    assert high_data["human_review_queue_id"] is not None

    # Verify queued item appears in GET /api/v1/agent/actions/review
    resp_queue = client.get("/api/v1/agent/actions/review")
    assert resp_queue.status_code == 200
    queued_ids = [item["request_id"] for item in resp_queue.json()]
    assert high_data["human_review_queue_id"] in queued_ids

    # 2. Dispatch <= 500 EUR with verified address is AUTONOMOUSLY_APPROVED
    resp_low = client.post(
        "/api/v1/agent/actions/dispatch",
        json={
            "parcel_id": "PKG-STD-111",
            "declared_value_eur": 150.0,
            "address_verified": True,
        },
    )
    assert resp_low.status_code == 200
    assert resp_low.json()["decision"] == "AUTONOMOUSLY_APPROVED"




