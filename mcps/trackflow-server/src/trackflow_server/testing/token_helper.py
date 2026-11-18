"""OAuth 2.1 JWT token generation helpers for development, CLI validation, and testing."""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Union

import jwt

DEFAULT_JWT_SECRET = "trackflow-mcp-oauth-secret-key-2026-hs256-secure"
DEFAULT_ISSUER = "https://auth.trackflow.local"
DEFAULT_AUDIENCE = "https://api.trackflow.local/mcp/"
ALL_SCOPES: Sequence[str] = (
    "incidents:read",
    "incidents:write",
    "incidents:lifecycle",
    "inventory:read",
)


def get_jwt_secret() -> str:
    """Return the configured JWT signing secret."""
    return os.environ.get("MCP_JWT_SECRET", DEFAULT_JWT_SECRET)


def get_oauth_issuer() -> str:
    """Return the expected OAuth 2.1 token issuer URL."""
    return os.environ.get("MCP_OAUTH_ISSUER", DEFAULT_ISSUER)


def get_oauth_audience() -> str:
    """Return the expected OAuth 2.1 audience / resource indicator."""
    return os.environ.get("MCP_OAUTH_AUDIENCE", DEFAULT_AUDIENCE)


def create_access_token(
    *,
    scopes: Optional[Union[str, Sequence[str]]] = None,
    client_id: str = "trackflow-agent-client",
    subject: str = "agent-service-account",
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    expires_in_seconds: int = 3600,
    secret: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Mint a signed OAuth 2.1 JWT Bearer token for testing or internal agent auth.

    Args:
        scopes: Granted scopes as a space-separated string or list of scope strings.
                Defaults to all 4 scopes if None.
        client_id: OAuth client identifier.
        subject: Token subject (`sub`).
        issuer: Token issuer (`iss`).
        audience: Token audience (`aud`).
        expires_in_seconds: Token lifetime in seconds (negative for expired token tests).
        secret: Signing secret override.
        extra_claims: Optional additional JWT claims.

    Returns:
        Encoded HS256 JWT string.
    """
    if scopes is None:
        scope_list = list(ALL_SCOPES)
    elif isinstance(scopes, str):
        scope_list = [s for s in scopes.strip().split() if s]
    else:
        scope_list = [str(s).strip() for s in scopes if str(s).strip()]

    now = int(time.time())
    payload: Dict[str, Any] = {
        "iss": issuer if issuer is not None else get_oauth_issuer(),
        "aud": audience if audience is not None else get_oauth_audience(),
        "sub": subject,
        "client_id": client_id,
        "scope": " ".join(scope_list),
        "scopes": scope_list,
        "iat": now - 60 if expires_in_seconds < 0 else now,
        "exp": now + int(expires_in_seconds),
    }
    if extra_claims:
        payload.update(extra_claims)

    signing_key = secret if secret is not None else get_jwt_secret()
    return jwt.encode(payload, signing_key, algorithm="HS256")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint to output a signed test Bearer token to stdout."""
    parser = argparse.ArgumentParser(
        description="Generate a signed OAuth 2.1 Bearer JWT for TrackFlow MCP Server testing."
    )
    parser.add_argument(
        "--scope",
        default=" ".join(ALL_SCOPES),
        help="Space-separated list of OAuth scopes to grant.",
    )
    parser.add_argument(
        "--client-id",
        default="trackflow-cli-inspector",
        help="OAuth client_id claim.",
    )
    parser.add_argument(
        "--subject",
        default="developer-cli",
        help="OAuth sub claim.",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=3600,
        help="Expiration offset in seconds (default: 3600).",
    )
    args = parser.parse_args(argv)
    token = create_access_token(
        scopes=args.scope,
        client_id=args.client_id,
        subject=args.subject,
        expires_in_seconds=args.expires_in,
    )
    sys.stdout.write(token + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
