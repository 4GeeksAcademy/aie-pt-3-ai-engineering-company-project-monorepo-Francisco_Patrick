"""TrackFlow API composition root.

Builds the FastAPI application, registers cross-cutting concerns (CORS, exception
handlers, lifecycle) and mounts every router twice:

* canonical versioned paths under ``/api/v1/*``
* legacy paths (``/suppliers``, ``/inventory``, ``/auth``, ``/users``, ``/profiles``,
  ``/api/incidents``, ``/telemetry``) kept for 100% backward compatibility.

No business logic or module-level state lives here; collaborators are resolved
through the providers in ``presentation.dependencies``.
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Tuple

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add monorepo root and api dir to sys.path so shared and local modules resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.exceptions import register_exception_handlers  # noqa: E402
from infrastructure.persistence.sqlmodel.client import init_db  # noqa: E402
from presentation.api.v1 import (  # noqa: E402
    agent,
    auth,
    incidents,
    inventory,
    knowledge,
    memory,
    profiles,
    rfp,
    security_audit,
    suppliers,
    tasks,
    telemetry,
    users,
)
from presentation.dependencies import get_security_adapter_dep  # noqa: E402
from services.reporting.presentation import routes as reporting  # noqa: E402

API_V1_PREFIX = "/api/v1"

# (router, canonical v1 prefix, legacy prefix)
ROUTE_TABLE: List[Tuple[APIRouter, str, str]] = [
    (suppliers.router, f"{API_V1_PREFIX}/suppliers", "/suppliers"),
    (inventory.router, f"{API_V1_PREFIX}/inventory", "/inventory"),
    (incidents.router, f"{API_V1_PREFIX}/incidents", "/api/incidents"),
    (auth.router, f"{API_V1_PREFIX}/auth", "/auth"),
    (users.router, f"{API_V1_PREFIX}/users", "/users"),
    (profiles.router, f"{API_V1_PREFIX}/profiles", "/profiles"),
    (telemetry.router, f"{API_V1_PREFIX}/telemetry", "/telemetry"),
    (reporting.router, f"{API_V1_PREFIX}/reporting", "/reporting"),
    (tasks.router, f"{API_V1_PREFIX}/tasks", "/tasks"),
    (knowledge.router, f"{API_V1_PREFIX}/knowledge", "/knowledge"),
    (agent.router, f"{API_V1_PREFIX}/agent", "/agent"),
    (memory.router, f"{API_V1_PREFIX}/memory", "/memory"),
    (memory.router, f"{API_V1_PREFIX}/agent/memory", "/agent/memory"),
    (rfp.router, f"{API_V1_PREFIX}/rfp", "/rfp"),
    (security_audit.router, f"{API_V1_PREFIX}/security-audit", "/security-audit"),
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize relational schemas on startup."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Fully wired FastAPI instance with dual (v1 + legacy) route mounting.

    Raises:
        RuntimeError: Propagated from the security adapter when JWT_SECRET_KEY is missing.
    """
    # Fail fast on missing JWT configuration instead of on the first request.
    get_security_adapter_dep()

    application = FastAPI(title="Incident Analyzer API", lifespan=lifespan)

    register_exception_handlers(application)

    for router, v1_prefix, legacy_prefix in ROUTE_TABLE:
        application.include_router(router, prefix=v1_prefix)
        application.include_router(router, prefix=legacy_prefix)

    # Configure hardened, explicit CORS origins (A05 Security Misconfiguration remediation)
    cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    if cors_origins_env and cors_origins_env != "*":
        allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "https://app.trackflow.io",
        ]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return application


app = create_app()
