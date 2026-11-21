"""Tests verifying Docker backend requirements manifest consistency.

Pins down bug fix for slug 'docker-backend-missing-langgraph' where
services/Dockerfile built the container image from services/api/requirements.txt,
which lacked langgraph, langgraph-checkpoint, langchain-mcp-adapters, fastmcp,
mcpauth, and other dependencies declared in pyproject.toml.
"""

from pathlib import Path
from typing import List
import pytest


def test_requirements_contains_langgraph_and_agent_dependencies() -> None:
    """Verify services/api/requirements.txt contains langgraph and all required agent dependencies."""
    repo_root = Path(__file__).resolve().parents[3]
    requirements_file = repo_root / "services" / "api" / "requirements.txt"
    assert requirements_file.exists(), f"requirements.txt not found at {requirements_file}"

    content = requirements_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    required_packages: List[str] = [
        "langgraph>=1.2.22",
        "langgraph-checkpoint>=4.3.2",
        "langchain-mcp-adapters>=0.3.2",
        "fastmcp>=3.4.11",
        "mcpauth>=0.1.1",
        "pyjwt>=2.15.1",
        "scikit-learn>=1.9.1",
        "scipy>=1.18.1",
        "matplotlib>=3.11.2",
        "burner-redis>=0.1.7",
        "amplitude-analytics>=1.3.0",
    ]

    for req in required_packages:
        pkg_name = req.split(">=")[0]
        matching_line = next((line for line in lines if line.startswith(pkg_name)), None)
        assert matching_line is not None, f"Required package '{pkg_name}' missing from services/api/requirements.txt"
        assert req in matching_line, (
            f"Package version constraint mismatch for '{pkg_name}': expected '{req}', found '{matching_line}'"
        )


def test_support_agent_service_and_langgraph_imports() -> None:
    """Verify LangGraph and SupportAgentService modules import successfully without ModuleNotFoundError."""
    try:
        import langgraph
        from langgraph.checkpoint.base import BaseCheckpointSaver
        import langchain_mcp_adapters
        from application.services.support_agent_service import SupportAgentService

        assert langgraph is not None
        assert BaseCheckpointSaver is not None
        assert langchain_mcp_adapters is not None
        assert SupportAgentService is not None
    except ModuleNotFoundError as e:
        pytest.fail(f"Module import failed: {e}")


def test_dockerfile_base_image_python_version() -> None:
    """Verify services/Dockerfile uses Python >= 3.12 base image to support scipy>=1.18.1."""
    repo_root = Path(__file__).resolve().parents[3]
    dockerfile = repo_root / "services" / "Dockerfile"
    assert dockerfile.exists(), f"Dockerfile not found at {dockerfile}"

    content = dockerfile.read_text(encoding="utf-8")
    first_line = content.splitlines()[0].strip()

    assert first_line.startswith("FROM python:3.12"), (
        f"Dockerfile must use python:3.12 base image to satisfy dependency requirements, found: '{first_line}'"
    )

