"""Security audit presentation router and retrieval endpoints.

Provides read-only access to the OWASP Top 10 security audit matrix,
individual security findings, and regulatory privacy compliance metrics.
Adheres strictly to Monorepo Constitution Principles I & II.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from presentation.schemas.security_audit import (
    AISystemRecordSchema,
    NISTAssessmentReportResponse,
    OWASPAuditMatrixResponse,
    ResidualRiskRecordSchema,
    SecurityFindingSchema,
    SharedResponsibilityRecordSchema,
)
from presentation.dependencies import get_nist_governance_repository_dep
from infrastructure.adapters.nist_governance_repository import NISTGovernanceRepository

router = APIRouter(tags=["Security Audit"])


def _find_repo_root() -> Path:
    """Resolve the monorepo root directory dynamically."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".specify").exists():
            return parent
    return Path.cwd()


def get_audit_matrix_data() -> Dict[str, Any]:
    """Load the compiled OWASP audit matrix JSON from the specifications directory.

    Returns:
        Raw dictionary representation conforming to OWASPAuditMatrixResponse.

    Raises:
        HTTPException: 500 if the audit matrix file is missing or corrupted.
    """
    root = _find_repo_root()
    matrix_path = root / "specs" / "036-owasp-audit-hardening" / "audit" / "owasp_audit_matrix.json"
    if not matrix_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security audit matrix artifact is missing or not yet generated.",
        )
    try:
        with open(matrix_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse security audit matrix: {exc}",
        ) from exc


@router.get(
    "",
    response_model=OWASPAuditMatrixResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the comprehensive tri-track OWASP Top 10 security audit matrix",
)
async def get_security_audit_matrix(
    data: Dict[str, Any] = Depends(get_audit_matrix_data),
) -> OWASPAuditMatrixResponse:
    """Return the complete security audit matrix across Backend, Frontend, and Agentic components."""
    return OWASPAuditMatrixResponse.model_validate(data)


@router.get(
    "/findings",
    response_model=List[SecurityFindingSchema],
    status_code=status.HTTP_200_OK,
    summary="List security findings with optional component and severity filters",
)
async def list_security_findings(
    component: Optional[str] = Query(
        None, description="Filter findings by component (BACKEND, FRONTEND, AGENTIC, HOST)"
    ),
    severity: Optional[str] = Query(
        None, description="Filter findings by severity (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL)"
    ),
    data: Dict[str, Any] = Depends(get_audit_matrix_data),
) -> List[SecurityFindingSchema]:
    """Return filtered list of security findings."""
    matrix = OWASPAuditMatrixResponse.model_validate(data)
    results = matrix.findings

    if component:
        comp_upper = component.upper()
        results = [f for f in results if f.component == comp_upper]

    if severity:
        sev_upper = severity.upper()
        results = [f for f in results if f.severity == sev_upper]

    return results


@router.get(
    "/findings/{finding_id}",
    response_model=SecurityFindingSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve details for a specific security finding by ID",
)
async def get_security_finding_by_id(
    finding_id: str,
    data: Dict[str, Any] = Depends(get_audit_matrix_data),
) -> SecurityFindingSchema:
    """Return a single security finding by its identifier (e.g. SEC-BK-001)."""
    matrix = OWASPAuditMatrixResponse.model_validate(data)
    for finding in matrix.findings:
        if finding.id.upper() == finding_id.upper():
            return finding

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Security finding '{finding_id}' not found.",
    )


# ---------------------------------------------------------------------------
# NIST CSF 2.0 & AI Governance Retrieval Endpoints (FR-001, FR-005, FR-006)
# ---------------------------------------------------------------------------

@router.get(
    "/nist-csf",
    response_model=NISTAssessmentReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve 6-Function NIST CSF 2.0 Assessment Report",
)
async def get_nist_csf_report(
    repo: NISTGovernanceRepository = Depends(get_nist_governance_repository_dep),
) -> NISTAssessmentReportResponse:
    """Return the complete cybersecurity framework assessment across all 6 functions."""
    try:
        data = repo.get_csf_report()
        return NISTAssessmentReportResponse.model_validate(data)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="NIST CSF baseline report artifact is missing.",
        ) from exc


@router.get(
    "/ai-inventory",
    response_model=List[AISystemRecordSchema],
    status_code=status.HTTP_200_OK,
    summary="List Authoritative AI Systems Inventory",
)
async def list_ai_systems_inventory(
    repo: NISTGovernanceRepository = Depends(get_nist_governance_repository_dep),
) -> List[AISystemRecordSchema]:
    """Return all 5 operational AI components with internal custodians and attack surfaces."""
    try:
        data = repo.list_ai_inventory()
        return [AISystemRecordSchema.model_validate(item) for item in data]
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI systems inventory catalog artifact is missing.",
        ) from exc


@router.get(
    "/shared-responsibility",
    response_model=List[SharedResponsibilityRecordSchema],
    status_code=status.HTTP_200_OK,
    summary="List Third-Party AI Shared Responsibility Matrix",
)
async def list_shared_responsibility_matrix(
    repo: NISTGovernanceRepository = Depends(get_nist_governance_repository_dep),
) -> List[SharedResponsibilityRecordSchema]:
    """Return demarcated security obligations for external AI and courier providers."""
    try:
        data = repo.list_shared_responsibility()
        return [SharedResponsibilityRecordSchema.model_validate(item) for item in data]
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shared responsibility matrix artifact is missing.",
        ) from exc


@router.get(
    "/residual-risks",
    response_model=List[ResidualRiskRecordSchema],
    status_code=status.HTTP_200_OK,
    summary="List Residual Security Risks and Remediation Milestones",
)
async def list_residual_risks(
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"),
    function: Optional[str] = Query(
        None, description="Filter by NIST function: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER"
    ),
    repo: NISTGovernanceRepository = Depends(get_nist_governance_repository_dep),
) -> List[ResidualRiskRecordSchema]:
    """Return filtered list of residual risks with compensatory controls and milestones."""
    try:
        data = repo.list_residual_risks(severity=severity, nist_function=function)
        return [ResidualRiskRecordSchema.model_validate(item) for item in data]
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Residual risks ledger artifact is missing.",
        ) from exc
