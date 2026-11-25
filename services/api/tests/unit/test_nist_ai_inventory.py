"""Unit tests verifying authoritative AI systems inventory catalog and custodian mapping (US1, FR-005, SC-001)."""

import pytest
from infrastructure.adapters.nist_governance_repository import NISTGovernanceRepository
from presentation.schemas.security_audit import AISystemRecordSchema


@pytest.fixture
def nist_repo() -> NISTGovernanceRepository:
    """Fixture providing a fresh NISTGovernanceRepository instance."""
    return NISTGovernanceRepository()


def test_ai_systems_inventory_catalog_completeness(nist_repo: NISTGovernanceRepository) -> None:
    """Verify that all 5 operational AI components are cataloged and validate against schema."""
    inventory = nist_repo.list_ai_inventory()
    assert len(inventory) == 5, f"Expected 5 cataloged AI systems, found {len(inventory)}"

    validated_records = [AISystemRecordSchema.model_validate(item) for item in inventory]
    system_ids = {r.system_id for r in validated_records}

    expected_ids = {
        "TF-AI-01-CX-AGENT",
        "TF-AI-02-CARRIER-ENGINE",
        "TF-AI-03-POLICIES-RAG",
        "TF-AI-04-RETURN-ENGINE",
        "TF-AI-05-MCP-SERVER",
    }
    assert system_ids == expected_ids


def test_ai_systems_custodian_teams_and_technical_leads(nist_repo: NISTGovernanceRepository) -> None:
    """Verify that every AI system has designated internal custodians and non-empty attack surfaces."""
    inventory = nist_repo.list_ai_inventory()
    records = {item["system_id"]: AISystemRecordSchema.model_validate(item) for item in inventory}

    # 1. 24/7 CX Agent
    cx_agent = records["TF-AI-01-CX-AGENT"]
    assert cx_agent.custodian_team == "AI & Agent Systems Team"
    assert cx_agent.data_classification == "RESTRICTED_PII"
    assert cx_agent.architecture_type == "AUTONOMOUS_AGENT"
    assert len(cx_agent.input_attack_surfaces) > 0
    assert cx_agent.requires_hitl_gates is True
    assert cx_agent.rate_limiting_enabled is True

    # 2. Carrier Selection Engine
    carrier_engine = records["TF-AI-02-CARRIER-ENGINE"]
    assert carrier_engine.custodian_team == "Logistics Intelligence Team"
    assert carrier_engine.data_classification == "CONFIDENTIAL_B2B"
    assert carrier_engine.architecture_type == "DECISION_ENGINE"
    assert len(carrier_engine.input_attack_surfaces) > 0
    assert carrier_engine.requires_hitl_gates is True

    # 3. Return Policies & SLA RAG
    rag_pipeline = records["TF-AI-03-POLICIES-RAG"]
    assert rag_pipeline.custodian_team == "AI Knowledge Systems Team"
    assert rag_pipeline.data_classification == "CONFIDENTIAL_B2B"
    assert rag_pipeline.architecture_type == "RAG_PIPELINE"
    assert len(rag_pipeline.input_attack_surfaces) > 0
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
