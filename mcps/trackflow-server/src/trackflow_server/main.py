"""CLI runner and server bootstrap for the TrackFlow MCP Server.

Supports:
- HTTP / Server-Sent Events (SSE) transport (`--transport sse --port 8001`) for remote consumption
- Streamable HTTP transport (`--transport http --port 8001`)
- Standard I/O transport (`--transport stdio`) for local process consumption
"""

import argparse
import os
import sys
from typing import List, Optional

import uvicorn


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser for the TrackFlow MCP Server."""
    parser = argparse.ArgumentParser(
        prog="trackflow-mcp",
        description="TrackFlow Standardized MCP Server (Incidents Manager & Read-Only Inventory)",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "http", "streamable-http", "stdio"],
        default=os.environ.get("MCP_TRANSPORT", "sse"),
        help="Transport protocol to run ('sse', 'http', 'streamable-http', or 'stdio'). Defaults to 'sse'.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "0.0.0.0"),
        help="Bind host for HTTP/SSE transport (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8001")),
        help="Bind port for HTTP/SSE transport (default: 8001).",
    )
    parser.add_argument(
        "--upstream-url",
        default=os.environ.get("TRACKFLOW_API_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the upstream TrackFlow FastAPI service.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run the TrackFlow MCP Server with the selected transport."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.upstream_url:
        os.environ["TRACKFLOW_API_BASE_URL"] = args.upstream_url

    from trackflow_server.app import create_asgi_app, get_mcp_server

    if args.transport == "stdio":
        from trackflow_server.auth.middleware import (
            set_current_security_context,
            verify_bearer_token,
        )

        stdio_token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
        if stdio_token:
            set_current_security_context(verify_bearer_token(stdio_token))
        mcp = get_mcp_server()
        mcp.run(transport="stdio")
        return 0

    asgi_app = create_asgi_app(transport="sse" if args.transport == "sse" else "http")
    uvicorn.run(asgi_app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
