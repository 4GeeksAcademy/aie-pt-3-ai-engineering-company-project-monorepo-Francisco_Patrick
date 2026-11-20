"""OAuth 2.1 Bearer verification middleware and mcpauth integration (T019)."""

from contextvars import ContextVar
import os
from typing import Any, List, Optional

import jwt
from mcpauth.exceptions import (
    BearerAuthExceptionCode,
    MCPAuthBearerAuthException,
    MCPAuthTokenVerificationException,
    MCPAuthTokenVerificationExceptionCode,
)
from mcpauth.middleware.create_bearer_auth import get_bearer_token_from_headers
from mcpauth.types import AuthInfo
from mcpauth.utils import create_verify_jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from trackflow_server.auth.metadata import (
    PROTECTED_RESOURCE_METADATA_PATH,
    create_mcp_auth_instance,
)
from trackflow_server.models.errors import (
    AuthenticationRequiredError,
    InsufficientScopeError,
)
from trackflow_server.models.schemas import OAuthSecurityContext
from trackflow_server.auth.config import (
    get_jwt_secret,
    get_oauth_audience,
    get_oauth_issuer,
    get_oauth_jwks_uri,
)

_security_context_var: ContextVar[Optional[OAuthSecurityContext]] = ContextVar(
    "trackflow_mcp_security_context", default=None
)

_mcpauth_context_var: ContextVar[Optional[AuthInfo]] = ContextVar(
    "mcp_auth_context", default=None
)

PUBLIC_PATHS = {
    "/health",
    PROTECTED_RESOURCE_METADATA_PATH,
    "/.well-known/oauth-authorization-server",
}


def get_current_security_context() -> Optional[OAuthSecurityContext]:
    """Return the validated OAuthSecurityContext for the current execution context."""
    ctx = _security_context_var.get()
    if ctx is not None:
        return ctx
    auth_info = _mcpauth_context_var.get()
    if auth_info is not None:
        aud = auth_info.audience
        aud_str = (
            aud[0]
            if isinstance(aud, list) and aud
            else (str(aud) if aud else get_oauth_audience())
        )
        return OAuthSecurityContext(
            client_id=auth_info.client_id or auth_info.subject or "authenticated-client",
            subject=auth_info.subject or auth_info.client_id or "authenticated-client",
            issuer=auth_info.issuer or get_oauth_issuer(),
            audience=aud_str,
            scopes=list(auth_info.scopes or []),
            expires_at=auth_info.claims.get("exp") if auth_info.claims else None,
        )
    return None


def get_current_mcpauth_info() -> Optional[AuthInfo]:
    """Return the validated `mcpauth.AuthInfo` for the current execution context."""
    return _mcpauth_context_var.get()


def set_current_security_context(
    ctx: Optional[OAuthSecurityContext],
) -> None:
    """Set or clear the current OAuthSecurityContext."""
    _security_context_var.set(ctx)
    if ctx is None:
        _mcpauth_context_var.set(None)
    else:
        _mcpauth_context_var.set(
            AuthInfo(
                token="",
                issuer=ctx.issuer,
                client_id=ctx.client_id,
                scopes=list(ctx.scopes),
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
        )


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

    Supports both OIDC JWKS verification (`mcpauth.utils.create_verify_jwt` when
    `MCP_OAUTH_JWKS_URI` is configured) and signed JWT verification (`HS256` / `RS256`).
    Validates signature, expiration (`exp`), issuer (`iss`), and audience (`aud`).

    Raises:
        AuthenticationRequiredError: If the token is missing, expired, tampered, or invalid.
    """
    if not token or not token.strip():
        raise AuthenticationRequiredError("Bearer token is empty.")

    cleaned_token = token.strip()
    expected_issuer = get_oauth_issuer()
    expected_audience = get_oauth_audience()
    jwks_uri = get_oauth_jwks_uri()

    if jwks_uri:
        try:
            jwks_verifier = create_verify_jwt(jwks_uri)
            auth_info = jwks_verifier(cleaned_token)
            claims = dict(auth_info.claims or {})
        except Exception as exc:
            raise AuthenticationRequiredError(
                "JWKS OAuth 2.1 token verification failed.",
                details={"reason": "invalid_token"},
            ) from exc
    else:
        secret = get_jwt_secret()
        if not secret:
            raise AuthenticationRequiredError(
                "Server authentication configuration error: MCP_JWT_SECRET is not configured.",
                details={"reason": "server_misconfigured"},
            )
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
    """ASGI middleware enforcing OAuth 2.1 Bearer authentication via `mcpauth` on all MCP endpoints.

    Uses `mcpauth`'s `get_bearer_token_from_headers` and `MCPAuth.bearer_auth_middleware`
    verifier pipeline while returning RFC 9728 `WWW-Authenticate` challenges and
    categorized TrackFlow error payloads (`AUTHENTICATION_REQUIRED` / `INSUFFICIENT_SCOPE`).
    """

    def __init__(
        self,
        app: Any,
        required_scopes: Optional[List[str]] = None,
    ) -> None:
        super().__init__(app)
        self._required_scopes = required_scopes
        self._mcp_auth = create_mcp_auth_instance(context_var=_mcpauth_context_var)
        # Construct the underlying mcpauth BearerAuthMiddleware class for resource validation
        self._mcpauth_middleware_cls = self._mcp_auth.bearer_auth_middleware(
            mcpauth_verify_token_adapter,
            audience=get_oauth_audience(),
            required_scopes=required_scopes,
            show_error_details=True,
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        try:
            raw_token = get_bearer_token_from_headers(request.headers)
        except MCPAuthBearerAuthException as exc:
            if exc.code == BearerAuthExceptionCode.MISSING_AUTH_HEADER:
                return self._unauthorized_response(
                    "Missing Authorization header. Provide 'Authorization: Bearer <token>'."
                )
            return self._unauthorized_response(
                "Malformed Authorization header. Expected 'Bearer <token>'."
            )

        try:
            security_ctx = verify_bearer_token(raw_token)
            auth_info = mcpauth_verify_token_adapter(raw_token)
        except AuthenticationRequiredError as exc:
            return self._unauthorized_response(exc.message, exc.details)

        if self._required_scopes:
            missing = [
                s for s in self._required_scopes if s not in set(auth_info.scopes)
            ]
            if missing:
                scope_err = InsufficientScopeError(
                    required_scope=missing[0],
                    granted_scopes=list(auth_info.scopes),
                )
                return JSONResponse(
                    status_code=403,
                    content=scope_err.to_dict(),
                )

        token_reset = _security_context_var.set(security_ctx)
        mcpauth_reset = _mcpauth_context_var.set(auth_info)
        try:
            request.state.security_context = security_ctx
            request.state.auth_info = auth_info
            return await call_next(request)
        finally:
            _security_context_var.reset(token_reset)
            _mcpauth_context_var.reset(mcpauth_reset)

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
    "get_current_mcpauth_info",
    "get_current_security_context",
    "mcpauth_verify_token_adapter",
    "set_current_security_context",
    "verify_bearer_token",
]
