"""OAuth 2.1 Bearer verification middleware and mcpauth integration (T019)."""

from contextvars import ContextVar
from typing import Any, List, Optional

import jwt
from mcpauth.exceptions import (
    MCPAuthTokenVerificationException,
    MCPAuthTokenVerificationExceptionCode,
)
from mcpauth.types import AuthInfo
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from trackflow_server.auth.metadata import PROTECTED_RESOURCE_METADATA_PATH
from trackflow_server.models.errors import (
    AuthenticationRequiredError,
    McpErrorCode,
)
from trackflow_server.models.schemas import OAuthSecurityContext
from trackflow_server.testing.token_helper import (
    get_jwt_secret,
    get_oauth_audience,
    get_oauth_issuer,
)

_security_context_var: ContextVar[Optional[OAuthSecurityContext]] = ContextVar(
    "trackflow_mcp_security_context", default=None
)

PUBLIC_PATHS = {
    "/health",
    PROTECTED_RESOURCE_METADATA_PATH,
    "/.well-known/oauth-authorization-server",
}


def get_current_security_context() -> Optional[OAuthSecurityContext]:
    """Return the validated OAuthSecurityContext for the current execution context."""
    return _security_context_var.get()


def set_current_security_context(
    ctx: Optional[OAuthSecurityContext],
) -> None:
    """Set or clear the current OAuthSecurityContext."""
    _security_context_var.set(ctx)


def _extract_scopes_from_claims(claims: dict[str, Any]) -> List[str]:
    """Extract normalized list of scope strings from JWT `scope` or `scopes` claims."""
    raw_scope = claims.get("scope")
    if isinstance(raw_scope, str):
        return [s.strip() for s in raw_scope.split() if s.strip()]
    if isinstance(raw_scope, list):
        return [str(s).strip() for s in raw_scope if str(s).strip()]

    raw_scopes = claims.get("scopes")
    if isinstance(raw_scopes, list):
        return [str(s).strip() for s in raw_scopes if str(s).strip()]
    if isinstance(raw_scopes, str):
        return [s.strip() for s in raw_scopes.split() if s.strip()]
    return []


def verify_bearer_token(token: str) -> OAuthSecurityContext:
    """Verify an OAuth 2.1 Bearer JWT and return an OAuthSecurityContext.

    Validates signature, expiration (`exp`), issuer (`iss`), and audience (`aud`).

    Raises:
        AuthenticationRequiredError: If the token is missing, expired, tampered, or invalid.
    """
    if not token or not token.strip():
        raise AuthenticationRequiredError("Bearer token is empty.")

    cleaned_token = token.strip()
    expected_issuer = get_oauth_issuer()
    expected_audience = get_oauth_audience()
    secret = get_jwt_secret()

    try:
        claims = jwt.decode(
            cleaned_token,
            secret,
            algorithms=["HS256"],
            issuer=expected_issuer,
            audience=expected_audience,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationRequiredError(
            "Access token has expired. Please renew your OAuth 2.1 token.",
            details={"reason": "token_expired"},
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthenticationRequiredError(
            "Access token issuer does not match trusted authorization server.",
            details={"reason": "invalid_issuer"},
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthenticationRequiredError(
            "Access token audience does not match this MCP resource server.",
            details={"reason": "invalid_audience"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationRequiredError(
            "Provided Bearer access token is malformed or has an invalid signature.",
            details={"reason": "invalid_token"},
        ) from exc

    scopes = _extract_scopes_from_claims(claims)
    client_id = str(
        claims.get("client_id")
        or claims.get("azp")
        or claims.get("sub")
        or "authenticated-client"
    )
    subject = str(claims.get("sub") or client_id)
    issuer = str(claims.get("iss") or expected_issuer)
    aud_claim = claims.get("aud")
    if isinstance(aud_claim, list):
        audience = str(aud_claim[0]) if aud_claim else expected_audience
    else:
        audience = str(aud_claim or expected_audience)
    expires_at = int(claims["exp"]) if "exp" in claims else None

    return OAuthSecurityContext(
        client_id=client_id,
        subject=subject,
        issuer=issuer,
        audience=audience,
        scopes=scopes,
        expires_at=expires_at,
    )


def mcpauth_verify_token_adapter(token: str) -> AuthInfo:
    """Adapter conforming to `mcpauth.VerifyAccessTokenFunction` returning `mcpauth.AuthInfo`."""
    try:
        ctx = verify_bearer_token(token)
    except AuthenticationRequiredError as exc:
        raise MCPAuthTokenVerificationException(
            MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN,
            cause=exc,
        ) from exc

    return AuthInfo(
        token=token,
        issuer=ctx.issuer,
        client_id=ctx.client_id,
        scopes=ctx.scopes,
        subject=ctx.subject,
        audience=ctx.audience,
        claims={
            "sub": ctx.subject,
            "iss": ctx.issuer,
            "aud": ctx.audience,
            "client_id": ctx.client_id,
            "scope": " ".join(ctx.scopes),
            "exp": ctx.expires_at,
        },
    )


class OAuthBearerResourceMiddleware(BaseHTTPMiddleware):
    """ASGI middleware enforcing OAuth 2.1 Bearer authentication on all MCP resource endpoints.

    Allows unauthenticated discovery on RFC 9728 `/.well-known/oauth-protected-resource`,
    `/.well-known/oauth-authorization-server`, and `/health`, while enforcing valid
    Bearer JWTs on `/sse`, `/messages/`, `/mcp`, and all tool endpoints.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization") or request.headers.get(
            "authorization"
        )
        if not auth_header:
            return self._unauthorized_response(
                "Missing Authorization header. Provide 'Authorization: Bearer <token>'."
            )

        parts = auth_header.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            return self._unauthorized_response(
                "Malformed Authorization header. Expected 'Bearer <token>'."
            )

        raw_token = parts[1].strip()
        try:
            security_ctx = verify_bearer_token(raw_token)
            # Also validate through mcpauth adapter for full mcpauth compatibility
            _ = mcpauth_verify_token_adapter(raw_token)
        except AuthenticationRequiredError as exc:
            return self._unauthorized_response(exc.message, exc.details)

        token_reset = _security_context_var.set(security_ctx)
        try:
            request.state.security_context = security_ctx
            return await call_next(request)
        finally:
            _security_context_var.reset(token_reset)

    @staticmethod
    def _unauthorized_response(
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> JSONResponse:
        err = AuthenticationRequiredError(message=message, details=details)
        www_auth = (
            f'Bearer error="invalid_token", '
            f'error_description="{message}", '
            f'resource_metadata="{PROTECTED_RESOURCE_METADATA_PATH}"'
        )
        return JSONResponse(
            status_code=401,
            content=err.to_dict(),
            headers={"WWW-Authenticate": www_auth},
        )


__all__ = [
    "OAuthBearerResourceMiddleware",
    "PUBLIC_PATHS",
    "get_current_security_context",
    "mcpauth_verify_token_adapter",
    "set_current_security_context",
    "verify_bearer_token",
]
