"""Integration tests for 6-Function NIST CSF 2.0 Report & Residual Risks API (Scenario 8, FR-001, FR-013, FR-014, SC-007).

Verifies that:
1. GET /api/v1/security-audit/nist-csf returns complete 6-function assessment with verified controls.
2. GET /api/v1/security-audit/residual-risks supports query filtering by severity and NIST function.
3. Transatlantic regulatory alignment indicates GDPR 72h AEPD compliance and CCPA/CPRA enforcement.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from presentation.api.v1.security_audit import router as security_audit_router
from presentation.schemas.security_audit import (
    NISTAssessmentReportResponse,
    ResidualRiskRecordSchema,
)


@pytest.fixture
def api_client():
    """Create a TestClient with security audit router mounted."""
    app = FastAPI()
    app.include_router(security_audit_router, prefix="/api/v1/security-audit")
    return TestClient(app)


def test_get_nist_csf_report_completeness_and_six_functions(api_client: TestClient) -> None:
    """Verify that the NIST CSF 2.0 report spans all 6 functions with concrete operational actions."""
    resp = api_client.get("/api/v1/security-audit/nist-csf")
    assert resp.status_code == 200, f"Failed with {resp.status_code}: {resp.text}"

    report = NISTAssessmentReportResponse.model_validate(resp.json())
    assert report.framework_version == "NIST CSF 2.0"
    assert "Zaragoza" in report.executive_sponsor or "Los Angeles" in report.executive_sponsor

    # Verify all 6 functions are populated
    functions = report.functions
    assert len(functions.GOVERN) >= 1
    assert len(functions.IDENTIFY) >= 1
    assert len(functions.PROTECT) >= 1
    assert len(functions.DETECT) >= 1
    assert len(functions.RESPOND) >= 1
    assert len(functions.RECOVER) >= 1

    # Verify regulatory alignment
    assert report.regulatory_alignment.gdpr_aepd_72h_sla_compliant is True
    assert report.regulatory_alignment.ccpa_cpra_rights_enforced is True
    assert "Zaragoza" in report.regulatory_alignment.primary_dpo_office


def test_residual_risks_filtering_by_severity_and_function(api_client: TestClient) -> None:
    """Verify that /residual-risks endpoint supports filtering by severity and NIST function."""
    # 1. Unfiltered query
    resp_all = api_client.get("/api/v1/security-audit/residual-risks")
    assert resp_all.status_code == 200
    all_risks = [ResidualRiskRecordSchema.model_validate(r) for r in resp_all.json()]
    assert len(all_risks) >= 2

    # 2. Filter by severity=MEDIUM
    resp_med = api_client.get("/api/v1/security-audit/residual-risks?severity=MEDIUM")
    assert resp_med.status_code == 200
    med_risks = [ResidualRiskRecordSchema.model_validate(r) for r in resp_med.json()]
    assert all(r.severity == "MEDIUM" for r in med_risks)
    assert any(r.risk_id == "RISK-NIST-PR-01" for r in med_risks)

    # 3. Filter by function=PROTECT
    resp_fn = api_client.get("/api/v1/security-audit/residual-risks?function=PROTECT")
    assert resp_fn.status_code == 200
    protect_risks = [ResidualRiskRecordSchema.model_validate(r) for r in resp_fn.json()]
    assert all(r.nist_function == "PROTECT" for r in protect_risks)
