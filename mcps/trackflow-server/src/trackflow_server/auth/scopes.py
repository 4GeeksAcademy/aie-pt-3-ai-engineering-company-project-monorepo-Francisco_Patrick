"""Fine-grained OAuth 2.1 scope permission matrix and enforcement helpers (T021)."""

from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional

from trackflow_server.models.errors import InsufficientScopeError
from trackflow_server.models.schemas import OAuthSecurityContext

TOOL_REQUIRED_SCOPES: Dict[str, str] = {
    "create_incident": "incidents:write",
    "query_incidents": "incidents:read",
    "transition_incident_status": "incidents:lifecycle",
    "query_inventory": "inventory:read",
}


def get_required_scope(tool_name: str) -> Optional[str]:
    """Return the required OAuth 2.1 scope for a given MCP tool name."""
    return TOOL_REQUIRED_SCOPES.get(tool_name)


def check_tool_scope(
    tool_name: str,
    security_context: Optional[OAuthSecurityContext],
) -> None:
    """Verify that `security_context` holds the required scope for `tool_name`.

    Args:
        tool_name: Name of the MCP tool being invoked.
        security_context: Validated OAuthSecurityContext of the caller.

    Raises:
        InsufficientScopeError: If the required scope is missing from the caller's token.
    """
    required_scope = get_required_scope(tool_name)
    if not required_scope:
        return

    if security_context is None:
        return

    granted = set(security_context.scopes or [])
    if required_scope not in granted:
        raise InsufficientScopeError(
            required_scope=required_scope,
            granted_scopes=list(security_context.scopes),
            tool_name=tool_name,
        )


def require_scope(
    scope: str,
    tool_name: Optional[str] = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator enforcing that the active security context possesses `scope`."""

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from trackflow_server.auth.middleware import get_current_security_context

            ctx = get_current_security_context()
            if ctx is not None and scope not in set(ctx.scopes):
                raise InsufficientScopeError(
                    required_scope=scope,
                    granted_scopes=list(ctx.scopes),
                    tool_name=tool_name or func.__name__,
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "TOOL_REQUIRED_SCOPES",
    "check_tool_scope",
    "get_required_scope",
    "require_scope",
]
