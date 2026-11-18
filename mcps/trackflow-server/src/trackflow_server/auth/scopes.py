"""Fine-grained OAuth 2.1 scope permission matrix and mcpauth required_scopes enforcement (T021)."""

from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional

from mcpauth.exceptions import (
    BearerAuthExceptionCode,
    MCPAuthBearerAuthException,
    MCPAuthBearerAuthExceptionDetails,
)
from mcpauth.middleware.create_bearer_auth import BearerAuthConfig

from trackflow_server.models.errors import (
    AuthenticationRequiredError,
    InsufficientScopeError,
)
from trackflow_server.models.schemas import OAuthSecurityContext
from trackflow_server.testing.token_helper import get_oauth_audience, get_oauth_issuer

TOOL_REQUIRED_SCOPES: Dict[str, str] = {
    "create_incident": "incidents:write",
    "query_incidents": "incidents:read",
    "transition_incident_status": "incidents:lifecycle",
    "query_inventory": "inventory:read",
}


def get_required_scope(tool_name: str) -> Optional[str]:
    """Return the required OAuth 2.1 scope for a given MCP tool name."""
    return TOOL_REQUIRED_SCOPES.get(tool_name)


def build_tool_bearer_auth_config(tool_name: str) -> BearerAuthConfig:
    """Build an `mcpauth.BearerAuthConfig` with `required_scopes` for `tool_name`."""
    required_scope = get_required_scope(tool_name)
    required_scopes: Optional[List[str]] = [required_scope] if required_scope else None
    return BearerAuthConfig(
        issuer=get_oauth_issuer(),
        audience=get_oauth_audience(),
        required_scopes=required_scopes,
        show_error_details=True,
    )


def check_tool_scope(
    tool_name: str,
    security_context: Optional[OAuthSecurityContext],
) -> None:
    """Verify that `security_context` is authenticated and holds `required_scopes` via `mcpauth`.

    Args:
        tool_name: Name of the MCP tool being invoked.
        security_context: Validated OAuthSecurityContext of the caller.

    Raises:
        AuthenticationRequiredError: If `security_context` is missing (unauthenticated caller).
        InsufficientScopeError: If the required scope is missing from the caller's token.
    """
    if security_context is None:
        raise AuthenticationRequiredError(
            f"Valid OAuth 2.1 Bearer access token is required to invoke tool '{tool_name}'."
        )

    config = build_tool_bearer_auth_config(tool_name)
    if not config.required_scopes:
        return

    granted = set(security_context.scopes or [])
    missing_scopes = [
        scope for scope in config.required_scopes if scope not in granted
    ]
    if missing_scopes:
        mcpauth_err = MCPAuthBearerAuthException(
            BearerAuthExceptionCode.MISSING_REQUIRED_SCOPES,
            cause=MCPAuthBearerAuthExceptionDetails(missing_scopes=missing_scopes),
        )
        raise InsufficientScopeError(
            required_scope=missing_scopes[0],
            granted_scopes=list(security_context.scopes),
            tool_name=tool_name,
        ) from mcpauth_err


def require_scope(
    scope: str,
    tool_name: Optional[str] = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator enforcing that the active security context is authenticated and possesses `scope`."""

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from trackflow_server.auth.middleware import get_current_security_context

            ctx = get_current_security_context()
            resolved_name = tool_name or func.__name__
            if ctx is None:
                raise AuthenticationRequiredError(
                    f"Valid OAuth 2.1 Bearer access token is required to invoke tool '{resolved_name}'."
                )
            if scope not in set(ctx.scopes):
                raise InsufficientScopeError(
                    required_scope=scope,
                    granted_scopes=list(ctx.scopes),
                    tool_name=resolved_name,
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "TOOL_REQUIRED_SCOPES",
    "build_tool_bearer_auth_config",
    "check_tool_scope",
    "get_required_scope",
    "require_scope",
]
