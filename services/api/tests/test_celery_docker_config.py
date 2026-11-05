"""Tests verifying Docker Compose Celery and Redis service configuration consistency."""

import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List
import yaml


def test_docker_compose_celery_services_have_redis_env() -> None:
    """Ensure all Celery-dependent services in docker-compose.yml define Redis URLs.

    Pins down bug fix for slug 'backend-redis-connection-lost' where backend container
    lacked REDIS_URL and CELERY_RESULT_BACKEND overrides, causing connection loss to Redis.
    """
    repo_root = Path(__file__).resolve().parents[3]
    compose_file = repo_root / "docker-compose.yml"
    assert compose_file.exists(), f"docker-compose.yml not found at {compose_file}"

    with compose_file.open("r", encoding="utf-8") as f:
        compose_data: Dict[str, Any] = yaml.safe_load(f)

    services: Dict[str, Any] = compose_data.get("services", {})
    celery_dependent_services: List[str] = ["backend", "worker", "flower"]

    for service_name in celery_dependent_services:
        assert service_name in services, f"Service '{service_name}' missing in docker-compose.yml"
        service = services[service_name]
        env_list: List[str] = service.get("environment", [])

        # Verify REDIS_URL is configured
        has_redis_url = any("REDIS_URL" in env_entry for env_entry in env_list)
        assert (
            has_redis_url
        ), f"Service '{service_name}' in docker-compose.yml is missing REDIS_URL environment variable"

        # Verify CELERY_RESULT_BACKEND is configured
        has_result_backend = any(
            "CELERY_RESULT_BACKEND" in env_entry for env_entry in env_list
        )
        assert (
            has_result_backend
        ), f"Service '{service_name}' in docker-compose.yml is missing CELERY_RESULT_BACKEND environment variable"

        # Verify fallback targets docker network service 'redis'
        redis_entries = [e for e in env_list if "REDIS_URL" in e]
        assert any(
            "redis://redis:6379" in e for e in redis_entries
        ), f"Service '{service_name}' REDIS_URL does not fallback to container hostname 'redis'"

        backend_entries = [e for e in env_list if "CELERY_RESULT_BACKEND" in e]
        assert any(
            "redis://redis:6379" in e for e in backend_entries
        ), f"Service '{service_name}' CELERY_RESULT_BACKEND does not fallback to container hostname 'redis'"


def test_sqlmodel_client_preserves_runtime_environment_variables() -> None:
    """Ensure importing SQLModel client does not overwrite existing process environment.

    Verifies that load_dotenv uses override=False so orchestrator-injected variables
    (e.g., REDIS_URL from docker-compose.yml) are preserved against services/api/.env defaults.
    """
    repo_root = Path(__file__).resolve().parents[3]
    python_code = (
        "import os\n"
        "import sys\n"
        "sys.path.insert(0, os.path.abspath('services/api'))\n"
        "sys.path.insert(0, os.path.abspath('.'))\n"
        "from infrastructure.persistence.sqlmodel.client import SQLModelClientManager\n"
        "assert os.environ.get('REDIS_URL') == 'redis://container-redis:6379/0', os.environ.get('REDIS_URL')\n"
        "assert os.environ.get('CELERY_RESULT_BACKEND') == 'redis://container-redis:6379/1', os.environ.get('CELERY_RESULT_BACKEND')\n"
    )
    env = os.environ.copy()
    env["REDIS_URL"] = "redis://container-redis:6379/0"
    env["CELERY_RESULT_BACKEND"] = "redis://container-redis:6379/1"
    env.pop("PYTEST_CURRENT_TEST", None)

    result = subprocess.run(
        [sys.executable, "-c", python_code],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Subprocess failed with stderr:\n{result.stderr}\nstdout:\n{result.stdout}"


