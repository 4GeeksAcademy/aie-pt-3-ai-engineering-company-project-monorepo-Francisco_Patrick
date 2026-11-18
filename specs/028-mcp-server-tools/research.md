# Phase 0 Research: Standardized MCP Server & Agent Integration

**Feature**: `028-mcp-server-tools`  
**Date**: 2026-11-18  
**Status**: Completed  

## 1. Architectural Decisions & Technology Choices

### Decision 1: Project Placement & Directory Architecture
- **Decision**: Create an independent Python package in `mcps/trackflow-server` managed via `uv` with its own `pyproject.toml`, alongside the existing backend in `services/api`.
- **Rationale**: 
  - Aligns with FR-001 and the established `mcps/` directory standard (`mcps/README.md`), which mandates that each subfolder inside `mcps/` corresponds to a single MCP server.
  - Keeps the MCP server lightweight, independently containerizable, and reusable across multiple internal services (like the support agent) and external API consumers.
  - Avoids polluting the FastAPI monolith while sharing domain DTO conventions.
- **Alternatives Considered**:
  - *Embedding directly inside `services/api/presentation/mcp/`*: Rejected because it tightly couples the MCP server lifecycle to the FastAPI monolith and violates the monorepo directory responsibility for `mcps/`.
  - *Generic single repository in root `src/`*: Rejected because the repo is an established multi-package monorepo (`services/api`, `uis/`, `packages/shared`, `mcps/`).

### Decision 2: MCP Server Framework (`fastmcp` vs Low-Level `mcp` SDK)
- **Decision**: Use `fastmcp` (v4.x) on top of the official `mcp` protocol engine.
- **Rationale**:
  - `fastmcp` provides clean, declarative `@mcp.tool()` decorators that generate compliant JSON Schema definitions, markdown descriptions, and typed parameter validation from Python type hints and Pydantic models (satisfies FR-002).
  - Native Starlette ASGI application export via `mcp.http_app(transport="sse")`, allowing seamless integration with authentication middleware and Starlette routes.
  - Full compatibility with the MCP specification, supporting tool discovery, error schemas, and cancellation tokens.
- **Alternatives Considered**:
  - *Low-level Python `mcp` SDK server*: Requires extensive manual boilerplate for JSON-RPC dispatching, tool list registration, and error serialization.
  - *Custom JSON-RPC server*: Rejected as it reinvents the wheel and risks non-conformance with MCP clients like Claude, Cursor, and LangChain.

### Decision 3: Transport Protocol (HTTP/SSE vs stdio)
- **Decision**: Primary transport is **HTTP with Server-Sent Events (SSE)** (and Streamable HTTP); stdio transport is supported via CLI command mode.
- **Rationale**:
  - Remote consumption by external automated clients, webhooks, and cloud-hosted environments (e.g. GitHub Codespaces forwarded ports, MCP Playground, remote agents) requires an HTTP-addressable endpoint (satisfies FR-003, FR-004, and Assumption on remote validation).
  - stdio requires spawning the server process as a local child process, which cannot be accessed by external network clients or protected by standard HTTP Bearer token headers in standard web environments.
  - FastMCP natively supports `fastmcp run --transport sse` or `mcp.run(transport="sse")`, which binds to `0.0.0.0:8001`, exposes `/sse` for event streaming, and accepts tool invocation POSTs to `/messages/`.
- **Alternatives Considered**:
  - *stdio-only transport*: Cannot be consumed over network/public URLs or integrated with standard HTTP OAuth reverse proxies.
  - *Raw WebSockets*: Higher operational complexity with less native client support in MCP toolkits compared to SSE.

### Decision 4: OAuth 2.1 / OIDC Resource Server Protection & Scope Architecture
- **Decision**: Utilize `mcpauth` (0.1.1) alongside custom ASGI middleware to publish Protected Resource Metadata (`/.well-known/oauth-protected-resource`) and enforce fine-grained scope authorization.
- **Rationale**:
  - Satisfies FR-003, FR-004, and FR-005. `mcpauth` provides `bearer_auth_middleware` for JWT validation against JWKS / OAuth authorization server metadata.
  - In development and test environments, an in-process or mock JWT verifier with HS256/RS256 secret tokens guarantees deterministic automated tests without external identity provider dependencies.
  - **Scope Matrix (Least Privilege)**:
    - `incidents:read`: Read-only access to query incidents by ID or filter criteria (`query_incidents`).
    - `incidents:write`: Permission to create new incident tickets (`create_incident`).
    - `incidents:lifecycle`: Permission to transition incident statuses (`transition_incident_status`).
    - `inventory:read`: Read-only access to query inventory stock records (`query_inventory`).
  - Missing token yields `401 Unauthorized` with `WWW-Authenticate: Bearer error="invalid_token"`. Missing scope yields `403 Forbidden` with error code `INSUFFICIENT_SCOPE`.
- **Alternatives Considered**:
  - *Static API Keys*: Fails FR-003 and modern enterprise agent security standards; cannot represent client identity or fine-grained scopes.
  - *No authentication*: Directly violates FR-003 and monorepo Constitution Principle IV.

### Decision 5: Incidents Tool Architecture & Lifecycle State Machine Enforcement
- **Decision**: Expose three dedicated incident tools (`create_incident`, `query_incidents`, `transition_incident_status`) delegating to the existing Incidents Manager API (`/api/incidents` and `/api/incidents/{id}/status`).
- **Rationale**:
  - FR-006 & FR-007 mandate that status transitions must strictly invoke `PATCH /api/incidents/{id}/status`. This ensures the domain lifecycle state machine (`open` -> `in_progress` -> `resolved` / `discarded`) is the single source of truth.
  - Field names (`id`, `title`, `description`, `status`, `category`, `origin`, `branch`, `created_at`, `updated_at`) directly mirror the domain model (FR-008).
  - Upstream network requests use `httpx.AsyncClient` with configured timeouts (4.0s) and pooled connections.
- **Alternatives Considered**:
  - *Direct TinyDB file read/write from MCP Server*: Strictly forbidden by Constitution Principle I ("Frontend and external services MUST NEVER directly access local backend database files (`db.json`)") and Principle II.

### Decision 6: Inventory Tool Read-Only Boundary & Structural Mutation Protection
- **Decision**: Expose a single read-only tool (`query_inventory`) and reject any mutation payload structurally.
- **Rationale**:
  - Satisfies FR-009, FR-010, and SC-002.
  - The tool schema explicitly accepts query parameters: `sku` (optional string), `product_id` (optional integer), `query` (optional free text search).
  - Any request containing mutation indicators (e.g. `action="adjust"`, `stock_delta`, `create_order`, `update`) is intercepted before execution and rejected with error code `INVENTORY_MUTATION_REJECTED` and HTTP 403 / MCP tool error.
  - No write tools (`create_product`, `adjust_stock`, `inbound_order`) are registered in the MCP tool registry.
- **Alternatives Considered**:
  - *Exposing a generic tool with an `action` enum that allows write*: Defeats structural isolation and risks accidental stock mutation if clients guess write parameters.

### Decision 7: LangGraph Agent Integration (`langchain-mcp-adapters`)
- **Decision**: Update `services/api/application/services/agent_workflow.py` and dependency injection in `presentation/dependencies.py` to use an MCP client adapter built with `langchain-mcp-adapters` (`load_mcp_tools` / `MultiServerMCPClient` or `SSEConnection`).
- **Rationale**:
  - Satisfies FR-013, FR-014, and FR-015.
  - The client adapter wraps the remote MCP tool calls and implements `SupportTicketToolPort`, maintaining clean hexagonal architecture.
  - The existing autonomous intake sanitization, mutation refusal guardrails, canonical ordering (`ticket_tool` -> `inventory_tool` -> `rag`), RAG routing, and fallback mechanisms remain untouched and fully covered by existing test suites.
  - Decommissions legacy direct tool calls without altering LangGraph node graph contracts.
- **Alternatives Considered**:
  - *Rewriting the agent to use raw LangChain agent executor*: Would dismantle the custom 7-node LangGraph state machine, state checkpointing, and fine-tuned routing logic. Wrapping MCP tools inside the existing port preserves all existing guarantees.

### Decision 8: Structured Audit Logging & Telemetry
- **Decision**: Implement an ASGI / FastMCP invocation middleware that logs structured JSON events for 100% of tool executions.
- **Rationale**:
  - Satisfies FR-011 and SC-005.
  - Logs capture: `timestamp`, `trace_id`, `client_id`, `tool_name`, sanitized parameters (PII and tokens redacted), `outcome` (`SUCCESS`, `REJECTED`, `ERROR`), and `latency_ms`.
  - Complies with Constitution Principle IV (Zero PII & Credential Leakage).

---

## 2. Best Practices & Dependency Management

- **Python Version**: `>=3.14` (consistent with `services/api/pyproject.toml`).
- **Dependency Tooling**: All new dependencies added via `uv add`:
  - In `mcps/trackflow-server`: `fastmcp>=4.2.1`, `mcpauth>=0.1.1`, `httpx>=0.28.1`, `pydantic>=2.14.0`, `pyjwt>=2.10.0`, `cryptography>=44.0.0`.
  - In `services/api`: `langchain-mcp-adapters>=0.3.1`.
- **Validation**: Zero TypeScript / compiler regressions, full pytest suite compatibility.
