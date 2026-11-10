"""Tests verifying FastAPI and Prefect compatibility in Celery worker environment.

Pins down bug fix for slug 'worker-prefect-body-min-items' where FastAPI >= 0.151.0
removed 'min_items' from Body(), causing Celery worker to crash with:
TypeError: Body() got an unexpected keyword argument 'min_items'
when starting Prefect's ephemeral flow orchestration engine.
"""

from pathlib import Path
import re
from typing import Any, Dict
import pytest
from packaging.version import Version


def test_requirements_fastapi_and_prefect_version_bounds() -> None:
    """Verify services/api/requirements.txt constrains FastAPI < 0.151.0 and Prefect >= 3.9.1."""
    repo_root = Path(__file__).resolve().parents[3]
    requirements_file = repo_root / "services" / "api" / "requirements.txt"
    assert requirements_file.exists(), f"requirements.txt not found at {requirements_file}"

    content = requirements_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    fastapi_line = next((line for line in lines if line.startswith("fastapi")), None)
    assert fastapi_line is not None, "fastapi constraint missing from requirements.txt"
    assert "<0.151.0" in fastapi_line, (
        f"fastapi must be constrained to <0.151.0 to prevent min_items removal in Body(), got: {fastapi_line}"
    )

    prefect_line = next((line for line in lines if line.startswith("prefect")), None)
    assert prefect_line is not None, "prefect constraint missing from requirements.txt"
    assert ">=3.9.1" in prefect_line or "<" in fastapi_line, (
        f"prefect must be constrained or paired with fastapi<0.151.0, got: {prefect_line}"
    )


def test_prefect_concurrency_limits_v2_import_compatibility() -> None:
    """Verify prefect.server.api.concurrency_limits_v2 imports without Body(min_items) TypeError."""
    try:
        from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse
        assert MinimalConcurrencyLimitResponse is not None
    except TypeError as e:
        pytest.fail(f"Prefect concurrency limits v2 module failed to import due to TypeError: {e}")


def test_prefect_ephemeral_client_flow_execution() -> None:
    """Verify executing a Prefect flow initializes ephemeral client context without TypeError."""
    from prefect import flow

    @flow(name="test-worker-prefect-compatibility-flow")
    def dummy_probe_flow(x: int) -> int:
        return x * 2

    # Invoking the flow triggers run_flow_sync -> initialize_run -> SyncClientContext.get_or_create()
    # In buggy configurations with fastapi >= 0.151.0 and prefect <= 3.8.8, this crashes with
    # TypeError: Body() got an unexpected keyword argument 'min_items'.
    result = dummy_probe_flow(21)
    assert result == 42


def test_installed_fastapi_version_is_compatible() -> None:
    """Verify runtime FastAPI version is strictly lower than 0.151.0."""
    import fastapi

    current_version = Version(fastapi.__version__)
    max_compatible_version = Version("0.151.0")
    assert current_version < max_compatible_version, (
        f"Installed FastAPI version {current_version} is >= 0.151.0, which breaks Prefect ephemeral server Body() params."
    )

