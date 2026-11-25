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


def test_docker_compose_internal_ports_bound_to_loopback(repo_root: Path) -> None:
    """Verify every published port in docker-compose.yml other than 3000/3001 starts with 127.0.0.1: and Flower removes admin:admin default."""
    import yaml

    compose_file = repo_root / "docker-compose.yml"
    assert compose_file.exists(), f"docker-compose.yml missing at {compose_file}"
    raw_text = compose_file.read_text(encoding="utf-8")
    compose_data = yaml.safe_load(raw_text)

    allowed_public_container_ports = {"3000", "3001"}
    internal_ports_found = set()

    for service_name, service_cfg in compose_data.get("services", {}).items():
        for port_mapping in service_cfg.get("ports", []):
            mapping_str = str(port_mapping)
            container_port = mapping_str.rsplit(":", 1)[-1].split("/")[0]
            if container_port in allowed_public_container_ports:
                continue
            internal_ports_found.add(container_port)
            assert mapping_str.startswith("127.0.0.1:"), (
                f"Service '{service_name}' publishes internal port '{mapping_str}' without 127.0.0.1: loopback binding"
            )

    assert {"8000", "6379", "5555"}.issubset(internal_ports_found)
    assert "admin:admin" not in raw_text, "docker-compose.yml must not default FLOWER_BASIC_AUTH to admin:admin"


def test_ufw_setup_covers_all_compose_internal_ports(repo_root: Path) -> None:
    """Verify every internal port in docker-compose.yml (8000, 6379, 5555) is also explicitly denied in ufw_setup.sh."""
    import yaml

    compose_file = repo_root / "docker-compose.yml"
    ufw_file = repo_root / "infra" / "host" / "ufw_setup.sh"
    compose_data = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    ufw_content = ufw_file.read_text(encoding="utf-8")

    allowed_public_container_ports = {"3000", "3001"}
    for service_name, service_cfg in compose_data.get("services", {}).items():
        for port_mapping in service_cfg.get("ports", []):
            mapping_str = str(port_mapping)
            container_port = mapping_str.rsplit(":", 1)[-1].split("/")[0]
            if container_port in allowed_public_container_ports:
                continue
            assert f"ufw deny {container_port}/tcp" in ufw_content, (
                f"Internal port {container_port} from service '{service_name}' is not covered by ufw_setup.sh"
            )

