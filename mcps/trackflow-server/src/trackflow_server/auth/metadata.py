"""RFC 9728 OAuth 2.0 Protected Resource Metadata endpoint and mcpauth configuration (T020)."""

from contextvars import ContextVar
import os
from typing import List, Optional

from mcpauth import MCPAuth
from mcpauth.config import (
    AuthorizationServerMetadata,
    AuthServerConfig,
    AuthServerType,
)
from mcpauth.types import AuthInfo
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from trackflow_server.models.schemas import ProtectedResourceMetadata
from trackflow_server.auth.config import (
    ALL_SCOPES,
    get_oauth_audience,
    get_oauth_issuer,
    get_oauth_jwks_uri,
)

PROTECTED_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"


def get_protected_resource_metadata() -> ProtectedResourceMetadata:
    """Build the RFC 9728 OAuth 2.0 Protected Resource Metadata model."""
    issuer = get_oauth_issuer().rstrip("/")
    resource = os.environ.get("MCP_RESOURCE_URL", get_oauth_audience())
    docs_url = os.environ.get(
        "MCP_RESOURCE_DOCS_URL",
        f"{resource.rstrip('/')}/docs",
    )
    return ProtectedResourceMetadata(
        resource=resource,
        authorization_servers=[issuer],
        scopes_supported=list(ALL_SCOPES),
        bearer_methods_supported=["header"],
        resource_documentation=docs_url,
    )


def create_mcp_auth_instance(
    context_var: Optional[ContextVar[Optional[AuthInfo]]] = None,
) -> MCPAuth:
    """Create and configure the `mcpauth.MCPAuth` instance for the authorization server."""
    issuer = get_oauth_issuer().rstrip("/")
    jwks_uri = get_oauth_jwks_uri() or f"{issuer}/.well-known/jwks.json"
    metadata = AuthorizationServerMetadata(
        issuer=issuer,
        authorization_endpoint=f"{issuer}/oauth/authorize",
        token_endpoint=f"{issuer}/oauth/token",
        jwks_uri=jwks_uri,
        registration_endpoint=f"{issuer}/oauth/register",
        response_types_supported=["code", "token"],
        grant_types_supported=["authorization_code", "client_credentials"],
        code_challenge_methods_supported=["S256"],
        scope_supported=list(ALL_SCOPES),
    )
    server_config = AuthServerConfig(
        metadata=metadata,
        type=AuthServerType.OAUTH,
    )
    if context_var is not None:
        return MCPAuth(server=server_config, context_var=context_var)
    return MCPAuth(server=server_config)


async def protected_resource_metadata_endpoint(request: Request) -> Response:
    """Starlette handler serving RFC 9728 `/.well-known/oauth-protected-resource`."""
    if request.method == "OPTIONS":
        response: Response = Response(status_code=204)
    else:
        meta = get_protected_resource_metadata()
        response = JSONResponse(
            meta.model_dump(exclude_none=True),
            status_code=200,
        )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


def create_metadata_routes(mcp_auth: MCPAuth) -> List[Route]:
    """Return Starlette routes for RFC 9728 Protected Resource Metadata and OAuth Server Metadata."""
    return [
        Route(
            PROTECTED_RESOURCE_METADATA_PATH,
            protected_resource_metadata_endpoint,
            methods=["GET", "OPTIONS"],
        ),
        mcp_auth.metadata_route(),
    ]


__all__ = [
    "PROTECTED_RESOURCE_METADATA_PATH",
    "create_mcp_auth_instance",
    "create_metadata_routes",
    "get_protected_resource_metadata",
    "protected_resource_metadata_endpoint",
]
