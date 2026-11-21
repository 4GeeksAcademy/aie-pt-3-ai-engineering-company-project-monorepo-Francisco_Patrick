"""Authentication, OAuth 2.1 metadata, and scope authorization package for TrackFlow MCP Server."""

from trackflow_server.auth.config import (
    ALL_SCOPES,
    DEFAULT_AUDIENCE,
    DEFAULT_ISSUER,
    get_jwt_secret,
    get_oauth_audience,
    get_oauth_issuer,
    get_oauth_jwks_uri,
    validate_auth_config,
)
from trackflow_server.auth.metadata import (
    PROTECTED_RESOURCE_METADATA_PATH,
    create_mcp_auth_instance,
    create_metadata_routes,
    get_protected_resource_metadata,
    protected_resource_metadata_endpoint,
)
from trackflow_server.auth.middleware import (
    OAuthBearerResourceMiddleware,
    PUBLIC_PATHS,
    get_current_security_context,
    mcpauth_verify_token_adapter,
    set_current_security_context,
    verify_bearer_token,
)
from trackflow_server.auth.scopes import (
    TOOL_REQUIRED_SCOPES,
    check_tool_scope,
    get_required_scope,
    require_scope,
)

__all__ = [
    "ALL_SCOPES",
    "DEFAULT_AUDIENCE",
    "DEFAULT_ISSUER",
    "OAuthBearerResourceMiddleware",
    "PROTECTED_RESOURCE_METADATA_PATH",
    "PUBLIC_PATHS",
    "TOOL_REQUIRED_SCOPES",
    "check_tool_scope",
    "create_mcp_auth_instance",
    "create_metadata_routes",
    "get_current_security_context",
    "get_jwt_secret",
    "get_oauth_audience",
    "get_oauth_issuer",
    "get_oauth_jwks_uri",
    "get_protected_resource_metadata",
    "get_required_scope",
    "mcpauth_verify_token_adapter",
    "protected_resource_metadata_endpoint",
    "require_scope",
    "set_current_security_context",
    "validate_auth_config",
    "verify_bearer_token",
]
