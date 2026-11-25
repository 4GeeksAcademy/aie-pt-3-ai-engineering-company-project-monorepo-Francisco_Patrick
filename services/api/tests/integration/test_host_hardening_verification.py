"""Integration test verifying host hardening configuration parsing and compliance rules."""

import json
from pathlib import Path
import pytest


@pytest.fixture
def repo_root() -> Path:
    """Find repository root directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".specify").exists():
            return parent
    return Path.cwd()


def test_sshd_config_hardened_rules(repo_root: Path) -> None:
    """Verify sshd_config.hardened contains mandatory security directives."""
    sshd_file = repo_root / "infra" / "host" / "sshd_config.hardened"
    assert sshd_file.exists(), f"sshd_config.hardened missing at {sshd_file}"
    content = sshd_file.read_text(encoding="utf-8").lower()
    
    assert "permitrootlogin no" in content
    assert "passwordauthentication no" in content
    assert "maxauthtries 3" in content
    assert "x11forwarding no" in content


def test_ufw_setup_script(repo_root: Path) -> None:
    """Verify ufw_setup.sh enforces default deny and whitelists 22, 80, 443."""
    ufw_file = repo_root / "infra" / "host" / "ufw_setup.sh"
    assert ufw_file.exists(), f"ufw_setup.sh missing at {ufw_file}"
    content = ufw_file.read_text(encoding="utf-8")
    
    assert "ufw default deny incoming" in content
    assert "ufw allow 22/tcp" in content
    assert "ufw allow 80/tcp" in content
    assert "ufw allow 443/tcp" in content


def test_permissions_setup_script(repo_root: Path) -> None:
    """Verify permissions_setup.sh restricts secrets to 0600."""
    perm_file = repo_root / "infra" / "host" / "permissions_setup.sh"
    assert perm_file.exists(), f"permissions_setup.sh missing at {perm_file}"
    content = perm_file.read_text(encoding="utf-8")
    
    assert "chmod 600" in content or "chmod 0600" in content
    assert ".env" in content


def test_verify_hardening_script(repo_root: Path) -> None:
    """Verify verify_hardening.sh performs automated compliance checks."""
    verify_file = repo_root / "infra" / "host" / "verify_hardening.sh"
    assert verify_file.exists(), f"verify_hardening.sh missing at {verify_file}"
    content = verify_file.read_text(encoding="utf-8")
    
    assert "PermitRootLogin" in content or "permitrootlogin" in content
    assert "ufw" in content


def test_verify_hardening_strictly_checks_system_without_false_positives(repo_root: Path) -> None:
    """Verify verify_hardening.sh does not falsely pass unhardened hosts by falling back to repo templates."""
    verify_file = repo_root / "infra" / "host" / "verify_hardening.sh"
    content = verify_file.read_text(encoding="utf-8")

    # Strict mode must require actual /etc/ssh/sshd_config on host
    assert "/etc/ssh/sshd_config" in content
    # Ensure there is no unconditional inline || grep fallback to templates in the host check
    assert "|| grep -Eqi \"^\\s*PermitRootLogin\\s+no\" infra/host/sshd_config.hardened" not in content
    # Ensure explicit --template-check flag is supported for CI/offline use
    assert "--template-check" in content
