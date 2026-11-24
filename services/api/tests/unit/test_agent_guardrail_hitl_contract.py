"""Contract test for agent guardrail HITL payload validation.

Validates payload conformance against contracts/agent-guardrail-hitl.schema.json
and Pydantic model AgentGuardrailHITLPayload.
"""

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
