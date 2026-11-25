"""Unit tests verifying authoritative AI systems inventory catalog and custodian mapping (US1, FR-005, SC-001)."""

import pytest
from infrastructure.adapters.nist_governance_repository import NISTGovernanceRepository
from presentation.schemas.security_audit import AISystemRecordSchema


@pytest.fixture
def nist_repo() -> NISTGovernanceRepository:
    """Fixture providing a fresh NISTGovernanceRepository instance."""
    return NISTGovernanceRepository()


def test_ai_systems_inventory_catalog_completeness(nist_repo: NISTGovernanceRepository) -> None:
    """Verify that all 9 operational AI components built in the monorepo are cataloged and validate against schema."""
    inventory = nist_repo.list_ai_inventory()
    assert len(inventory) == 9, f"Expected 9 cataloged AI systems, found {len(inventory)}"

    validated_records = [AISystemRecordSchema.model_validate(item) for item in inventory]
    system_ids = {r.system_id for r in validated_records}

    expected_ids = {
        "TF-AI-01-CX-AGENT",
        "TF-AI-02-CARRIER-ENGINE",
        "TF-AI-03-POLICIES-RAG",
        "TF-AI-04-RETURN-ENGINE",
        "TF-AI-05-MCP-SERVER",
        "TF-AI-06-RFP-WORKFLOW",
        "TF-AI-07-WEBSOCKET-CHAT",
        "TF-AI-08-AGENT-MEMORY",
        "TF-AI-09-SALES-FORECAST",
    }
    assert system_ids == expected_ids


def test_ai_systems_custodian_teams_and_technical_leads(nist_repo: NISTGovernanceRepository) -> None:
    """Verify that every AI system has designated internal custodians and non-empty attack surfaces."""
    inventory = nist_repo.list_ai_inventory()
    records = {item["system_id"]: AISystemRecordSchema.model_validate(item) for item in inventory}

    for sys_id, record in records.items():
        assert len(record.custodian_team.strip()) > 0, f"{sys_id} missing custodian_team"
        assert len(record.technical_lead.strip()) > 0, f"{sys_id} missing technical_lead"
        assert len(record.input_attack_surfaces) > 0, f"{sys_id} missing input_attack_surfaces"

    # 1. 24/7 CX Agent
    cx_agent = records["TF-AI-01-CX-AGENT"]
    assert cx_agent.custodian_team == "AI & Agent Systems Team"
    assert cx_agent.data_classification == "RESTRICTED_PII"
    assert cx_agent.architecture_type == "AUTONOMOUS_AGENT"
    assert cx_agent.requires_hitl_gates is True
    assert cx_agent.rate_limiting_enabled is True

    # 2. Carrier Selection Engine
    carrier_engine = records["TF-AI-02-CARRIER-ENGINE"]
    assert carrier_engine.custodian_team == "Logistics Intelligence Team"
    assert carrier_engine.data_classification == "CONFIDENTIAL_B2B"
    assert carrier_engine.architecture_type == "DECISION_ENGINE"
    assert carrier_engine.requires_hitl_gates is True

    # 3. Return Policies & SLA RAG
    rag_pipeline = records["TF-AI-03-POLICIES-RAG"]
    assert rag_pipeline.custodian_team == "AI Knowledge Systems Team"
    assert rag_pipeline.data_classification == "CONFIDENTIAL_B2B"
    assert rag_pipeline.architecture_type == "RAG_PIPELINE"
    assert rag_pipeline.rate_limiting_enabled is True

    # 4. Return Approval Engine
    return_engine = records["TF-AI-04-RETURN-ENGINE"]
    assert return_engine.custodian_team == "Reverse Logistics Team"
    assert return_engine.data_classification == "RESTRICTED_PII"
    assert return_engine.architecture_type == "DECISION_ENGINE"
    assert return_engine.requires_hitl_gates is True

    # 5. MCP Server Tool
    mcp_tool = records["TF-AI-05-MCP-SERVER"]
    assert mcp_tool.custodian_team == "Platform Architecture Team"
    assert mcp_tool.data_classification == "RESTRICTED_PII"
    assert mcp_tool.architecture_type == "MCP_SERVER_TOOL"
    assert mcp_tool.requires_hitl_gates is True
    assert mcp_tool.rate_limiting_enabled is True

    # 6. RFP Multi-Agent Workflow (Intake, Generation & Approval)
    rfp_workflow = records["TF-AI-06-RFP-WORKFLOW"]
    assert rfp_workflow.custodian_team == "B2B Commercial AI Team"
    assert rfp_workflow.data_classification == "CONFIDENTIAL_B2B"
    assert rfp_workflow.architecture_type == "AUTONOMOUS_AGENT"
    assert rfp_workflow.requires_hitl_gates is True
    assert rfp_workflow.rate_limiting_enabled is True

    # 7. WebSocket Streaming Chat & Event Broker
    ws_chat = records["TF-AI-07-WEBSOCKET-CHAT"]
    assert ws_chat.custodian_team == "AI & Agent Systems Team"
    assert ws_chat.data_classification == "RESTRICTED_PII"
    assert ws_chat.architecture_type == "AUTONOMOUS_AGENT"
    assert ws_chat.requires_hitl_gates is True
    assert ws_chat.rate_limiting_enabled is True

    # 8. Agent Memory & Self-Improvement Subsystem
    agent_memory = records["TF-AI-08-AGENT-MEMORY"]
    assert agent_memory.custodian_team == "AI Knowledge Systems Team"
    assert agent_memory.data_classification == "INTERNAL_OPERATIONAL"
    assert agent_memory.architecture_type == "AUTONOMOUS_AGENT"
    assert agent_memory.requires_hitl_gates is True
    assert agent_memory.rate_limiting_enabled is True

    # 9. Sales Forecasting & Demand Prediction Pipeline
    sales_forecast = records["TF-AI-09-SALES-FORECAST"]
    assert sales_forecast.custodian_team == "Data Science & Forecasting Team"
    assert sales_forecast.data_classification == "CONFIDENTIAL_B2B"
    assert sales_forecast.architecture_type == "DECISION_ENGINE"
    assert sales_forecast.requires_hitl_gates is False
