"""Contract test validating host baseline schema adherence.

Validates infra/host/baseline_pre.json and infra/host/baseline_post.json
against contracts/host-hardening-baseline.schema.json
and Pydantic response models in presentation.schemas.security_audit.
"""

import json
from pathlib import Path
import pytest
from presentation.schemas.security_audit import HostHardeningBaselineResponse


@pytest.fixture
def repo_root() -> Path:
    """Find repository root directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".specify").exists():
            return parent
    return Path.cwd()


def test_baseline_pre_schema_adherence(repo_root: Path) -> None:
    """Validate baseline_pre.json adheres to schema."""
    pre_path = repo_root / "infra" / "host" / "baseline_pre.json"
    assert pre_path.exists(), f"baseline_pre.json missing at {pre_path}"
    with open(pre_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    validated = HostHardeningBaselineResponse.model_validate(data)
    assert validated.phase == "PRE_REMEDIATION"
    assert validated.ssh_config.permit_root_login is True
    assert validated.ssh_config.is_compliant is False


def test_baseline_post_schema_adherence(repo_root: Path) -> None:
    """Validate baseline_post.json adheres to schema and is fully compliant."""
    post_path = repo_root / "infra" / "host" / "baseline_post.json"
    assert post_path.exists(), f"baseline_post.json missing at {post_path}"
    with open(post_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    validated = HostHardeningBaselineResponse.model_validate(data)
    assert validated.phase == "POST_REMEDIATION"
    assert validated.ssh_config.permit_root_login is False
    assert validated.ssh_config.password_authentication is False
    assert validated.ssh_config.is_compliant is True
