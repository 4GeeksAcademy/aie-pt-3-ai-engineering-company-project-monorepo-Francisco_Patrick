"""Production OAuth 2.1 configuration and environment credential validation for TrackFlow MCP Server."""

import os
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_ISSUER: str = "https://auth.trackflow.local"
DEFAULT_AUDIENCE: str = "https://api.trackflow.local/mcp/"
ALL_SCOPES: Sequence[str] = (
    "incidents:read",
    "incidents:write",
    "incidents:lifecycle",
    "inventory:read",
)


def load_dotenv_if_present() -> None:
    """Load variables from .env file in current, repo, or parent directories if not already defined in environment."""
    try:
        from dotenv import find_dotenv, load_dotenv as _dotenv_load

        env_path = find_dotenv(usecwd=True)
        if not env_path:
            for parent in Path(__file__).resolve().parents:
                candidate = parent / ".env"
                if candidate.is_file():
                    env_path = str(candidate)
                    break
        if env_path:
            _dotenv_load(env_path, override=False)
            return
    except ImportError:
        pass

    # Built-in fallback parser if python-dotenv is not installed
    search_dirs = [
        Path.cwd(),
        *Path.cwd().parents,
        *Path(__file__).resolve().parents,
    ]
    seen = set()
    for directory in search_dirs:
        try:
            resolved = directory.resolve()
        except Exception:
            resolved = directory
        if resolved in seen:
            continue
        seen.add(resolved)
        env_file = resolved / ".env"
        if env_file.is_file():
            try:
                content = env_file.read_text(encoding="utf-8")
                for raw_line in content.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
            except Exception:
                pass
            break


def get_jwt_secret() -> Optional[str]:
    """Return configured JWT signing secret from environment or None if not set."""
    load_dotenv_if_present()
    secret = os.environ.get("MCP_JWT_SECRET", "").strip()
    return secret if secret else None


def get_oauth_jwks_uri() -> Optional[str]:
    """Return configured OAuth JWKS URI from environment or None if not set."""
    load_dotenv_if_present()
    jwks_uri = os.environ.get("MCP_OAUTH_JWKS_URI", "").strip()
    return jwks_uri if jwks_uri else None


def get_oauth_issuer() -> str:
    """Return configured OAuth 2.1 token issuer URL."""
    load_dotenv_if_present()
    return os.environ.get("MCP_OAUTH_ISSUER", DEFAULT_ISSUER).strip()


def get_oauth_audience() -> str:
    """Return configured OAuth 2.1 audience / resource indicator URL."""
    load_dotenv_if_present()
    return os.environ.get("MCP_OAUTH_AUDIENCE", DEFAULT_AUDIENCE).strip()


def validate_auth_config() -> None:
    """Fail-fast startup assertion: ensure required OAuth security credentials are configured.

    Raises:
        RuntimeError: If neither 'MCP_JWT_SECRET' nor 'MCP_OAUTH_JWKS_URI' is set in the environment or .env.
    """
    secret = get_jwt_secret()
    jwks_uri = get_oauth_jwks_uri()
    if not secret and not jwks_uri:
        raise RuntimeError(
            "MCP Server startup failed: either 'MCP_JWT_SECRET' or 'MCP_OAUTH_JWKS_URI' "
            "must be defined in environment or .env."
        )


__all__ = [
    "ALL_SCOPES",
    "DEFAULT_AUDIENCE",
    "DEFAULT_ISSUER",
    "get_jwt_secret",
    "get_oauth_audience",
    "get_oauth_issuer",
    "get_oauth_jwks_uri",
    "load_dotenv_if_present",
    "validate_auth_config",
]
