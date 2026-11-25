"""Integration test verifying completeness of the 8 audited subsystems and 30 discrete OWASP intersections."""

import json
from pathlib import Path
import pytest
from presentation.schemas.security_audit import OWASPAuditMatrixResponse

REQUIRED_SUBSYSTEMS = [
    "cx-support-agent",
    "carrier-selection-engine",
    "return-approval-engine",
    "return-policy-rag",
    "tracking-api",
    "operations-dashboard",
    "b2b-brand-portal",
    "host-server",
]

OWASP_CATEGORIES = [
    "A01_BROKEN_ACCESS_CONTROL",
    "A02_CRYPTOGRAPHIC_FAILURES",
    "A03_INJECTION",
    "A04_INSECURE_DESIGN",
    "A05_SECURITY_MISCONFIGURATION",
    "A06_VULNERABLE_COMPONENTS",
    "A07_AUTH_FAILURES",
    "A08_INTEGRITY_FAILURES",
    "A09_LOGGING_MONITORING_FAILURES",
    "A10_SSRF",
]

AUDIT_TRACKS = ["BACKEND", "FRONTEND", "AGENTIC"]


@pytest.fixture
def repo_root() -> Path:
    """Find repository root directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".specify").exists():
            return parent
    return Path.cwd()


@pytest.fixture
def audit_matrix_data(repo_root: Path) -> dict:
    """Load the generated audit matrix JSON file."""
    matrix_path = repo_root / "specs" / "036-owasp-audit-hardening" / "audit" / "owasp_audit_matrix.json"
    assert matrix_path.exists(), f"Audit matrix file missing at {matrix_path}"
    with open(matrix_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_subsystems_completeness(audit_matrix_data: dict) -> None:
    """Verify that all 8 required subsystems are present in scope records."""
    validated = OWASPAuditMatrixResponse.model_validate(audit_matrix_data)
    present_ids = {scope.service_id for scope in validated.scope_records}
    for req in REQUIRED_SUBSYSTEMS:
        assert req in present_ids, f"Required subsystem {req} is missing from scope records"


def test_tri_track_owasp_intersection_completeness(audit_matrix_data: dict) -> None:
    """Verify all 30 discrete intersections (10 categories x 3 tracks) are evaluated."""
    validated = OWASPAuditMatrixResponse.model_validate(audit_matrix_data)
    
    intersections = set()
    for finding in validated.findings:
        intersections.add((finding.component, finding.category))
    
    missing = []
    for track in AUDIT_TRACKS:
        for cat in OWASP_CATEGORIES:
            if (track, cat) not in intersections:
                missing.append(f"{track}:{cat}")
                
    assert not missing, f"Missing OWASP track intersections: {missing}"


def test_applicability_and_citations(audit_matrix_data: dict) -> None:
    """Verify that every finding has explicit applicability and required details when applicable."""
    validated = OWASPAuditMatrixResponse.model_validate(audit_matrix_data)
    for finding in validated.findings:
        assert finding.applicability in ("APPLIES", "DOES_NOT_APPLY")
        if finding.applicability == "APPLIES":
            assert finding.location, f"Finding {finding.id} applies but has empty location"
            assert finding.remediation_plan, f"Finding {finding.id} applies but has empty remediation plan"
        if finding.severity == "CRITICAL" and finding.applicability == "APPLIES":
            assert finding.verification_status in ("VERIFIED_RESOLVED", "MITIGATED")
            assert finding.verification_proof, f"Critical finding {finding.id} lacks verification proof"
