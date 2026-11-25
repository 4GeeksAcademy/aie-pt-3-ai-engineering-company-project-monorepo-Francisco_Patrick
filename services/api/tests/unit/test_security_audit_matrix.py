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


def test_critical_findings_require_diff_or_test_and_valid_commit_hash(
    repo_root: Path, audit_matrix_data: dict
) -> None:
    """Verify CRITICAL findings are only VERIFIED_RESOLVED when backed by a real branch diff and test, and commit_hash is a valid ancestor of HEAD."""
    import re
    import subprocess

    validated = OWASPAuditMatrixResponse.model_validate(audit_matrix_data)
    commit_hash = validated.audit_metadata.commit_hash

    # Verify commit_hash resolves via git cat-file and is an ancestor of HEAD
    cat_file = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_hash}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cat_file.returncode == 0, f"commit_hash {commit_hash} does not resolve to a valid git commit"

    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_hash, "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert is_ancestor.returncode == 0, f"commit_hash {commit_hash} is not an ancestor of HEAD"

    # Pre-OWASP baseline commit on main cannot be certified as the post-remediation audit commit
    assert not commit_hash.startswith("8f4091a"), (
        "commit_hash must not point to pre-audit commit 8f4091a"
    )

    # Load host baseline_post.json provenance to verify whether host claims are backed by measured live capture
    baseline_post_path = repo_root / "infra" / "host" / "baseline_post.json"
    baseline_post_data = json.loads(baseline_post_path.read_text(encoding="utf-8"))
    host_provenance = baseline_post_data.get("provenance")

    # Check every CRITICAL finding marked VERIFIED_RESOLVED
    critical_resolved = [
        f
        for f in validated.findings
        if f.severity == "CRITICAL" and f.verification_status == "VERIFIED_RESOLVED"
    ]
    for finding in critical_resolved:
        if finding.component == "HOST":
            assert host_provenance == "measured_host_capture", (
                f"HOST finding {finding.id} cannot be CRITICAL + VERIFIED_RESOLVED when "
                f"baseline_post.json provenance is '{host_provenance}' (requires 'measured_host_capture')"
            )

    expected_critical_ids = {"SEC-BK-005", "SEC-AG-002"}
    if host_provenance == "measured_host_capture":
        expected_critical_ids.add("SEC-HST-001")
    else:
        hst_findings = [f for f in validated.findings if f.id == "SEC-HST-001"]
        assert len(hst_findings) == 1
        assert not (
            hst_findings[0].severity == "CRITICAL"
            and hst_findings[0].verification_status == "VERIFIED_RESOLVED"
        ), "SEC-HST-001 must not be claimed as CRITICAL + VERIFIED_RESOLVED without a measured_host_capture"

    assert {f.id for f in critical_resolved} == expected_critical_ids, (
        f"Expected VERIFIED_RESOLVED CRITICAL findings {sorted(expected_critical_ids)}, got {[f.id for f in critical_resolved]}"
    )

    for finding in critical_resolved:
        assert finding.verification_proof, f"CRITICAL finding {finding.id} is missing verification_proof"
        test_matches = re.findall(r"(services/api/tests/[^\s,;]+\.py|test_[a-zA-Z0-9_]+\.py)", finding.verification_proof)
        assert test_matches, f"CRITICAL finding {finding.id} verification_proof must reference a verification test file"

        target_file = finding.location.split(":")[0].strip()
        target_path = repo_root / target_file
        assert target_path.exists(), f"Location {target_file} for {finding.id} does not exist"

        # Ensure the target file was actually added or modified relative to the pre-audit commit 8f4091a
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", "8f4091a", "HEAD", "--", target_file],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert diff_proc.stdout.strip(), (
            f"CRITICAL finding {finding.id} claims VERIFIED_RESOLVED on {target_file}, "
            "but that file has no diff relative to pre-audit baseline 8f4091a"
        )

