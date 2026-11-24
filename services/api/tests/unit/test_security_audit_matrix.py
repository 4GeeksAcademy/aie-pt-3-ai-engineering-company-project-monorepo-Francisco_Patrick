"""Contract test validating OWASP audit matrix schema adherence.

Validates specs/036-owasp-audit-hardening/audit/owasp_audit_matrix.json
against specs/036-owasp-audit-hardening/contracts/owasp-audit-matrix.schema.json
and Pydantic response models in presentation.schemas.security_audit.
"""

import json
from pathlib import Path
import pytest
from presentation.schemas.security_audit import OWASPAuditMatrixResponse


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


def test_audit_matrix_contract_schema_adherence(audit_matrix_data: dict) -> None:
    """Validate that the audit matrix JSON conforms to the contract schema."""
    # Validate via Pydantic model
    validated = OWASPAuditMatrixResponse.model_validate(audit_matrix_data)
    assert validated.audit_metadata.evaluator
    assert validated.audit_metadata.commit_hash
    assert len(validated.scope_records) >= 8
    assert len(validated.findings) >= 30


def test_finding_id_patterns(audit_matrix_data: dict) -> None:
    """Verify that every finding conforms to the canonical ID format."""
    validated = OWASPAuditMatrixResponse.model_validate(audit_matrix_data)
    valid_prefixes = ("SEC-BK-", "SEC-FE-", "SEC-AG-", "SEC-HST-")
    for finding in validated.findings:
        assert any(finding.id.startswith(prefix) for prefix in valid_prefixes), (
            f"Invalid finding id format: {finding.id}"
        )
