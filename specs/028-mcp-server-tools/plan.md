# Implementation Plan: MCP Server - Connecting your Agent to Company Tools

**Branch**: `028-mcp-server-tools` | **Date**: 2026-11-18 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/spec.md)

**Input**: Feature specification from `/specs/028-mcp-server-tools/spec.md`

## Summary

Decouple the current TrackFlow Support Agent operational tools to build an independent, standardized Model Context Protocol (MCP) Server in `mcps/trackflow-server` protected by OAuth 2.1 / OIDC. The MCP Server exposes comprehensive incident ticket management (`create_incident`, `query_incidents`, `transition_incident_status`) delegating to the Incidents Manager lifecycle API, and strictly read-only access to warehouse stock (`query_inventory`) with structural mutation rejection. The server uses FastMCP with HTTP/Server-Sent Events (SSE) as its primary transport for remote consumption and stdio as a local alternative, publishing Protected Resource Metadata per RFC 9728. Simultaneously, refactor the LangGraph Support Agent in `services/api/application/services/agent_workflow.py` to consume the MCP server using `langchain-mcp-adapters`, decommissioning legacy direct incident calls while keeping multi-source routing with the RAG pipeline intact.

## Technical Context

**Language/Version**: Python >=3.14 (managed via `uv`)  
**Primary Dependencies**:
- MCP Server (`mcps/trackflow-server`): `fastmcp>=4.2.1`, `mcpauth>=0.1.1`, `httpx>=0.28.1`, `pydantic>=2.14.0`, `pyjwt>=2.10.0`, `cryptography>=44.0.0`, `starlette>=1.10.0`
- Agent Service (`services/api`): `langchain-mcp-adapters>=0.3.1`, `langgraph>=1.2.22`  
**Storage**: Upstream backend databases (TinyDB `db.json` and SQLite `inventory.db` via FastAPI REST APIs)  
**Testing**: `pytest`, `pytest-cov`, `httpx` ASGI test client, `MultiServerMCPClient` mock client  
**Target Platform**: Linux / Windows / GitHub Codespaces cloud environments  
**Project Type**: MCP Microservice / Web Service + LangGraph Agent Adapter Refactoring  
**Performance Goals**: Tool invocation latency < 500ms p95; tool timeout hard limit at 4.0s; audit logging overhead < 5ms  
**Constraints**: Zero write access to inventory; strict lifecycle status validation; zero PII / token leaks in audit logs; remote-accessible HTTP/SSE transport  
**Scale/Scope**: 4 MCP tools, 1 MCP server service, 1 agent adapter integration, comprehensive test suite  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Principle | Status | Evaluation & Mitigation |
|---|---|---|
| **I. Service Boundaries & Domain Isolation** | **PASS** | `mcps/trackflow-server` is an isolated package under `mcps/` communicating with `services/api` solely through HTTP REST endpoints (`/api/incidents`, `/api/v1/inventory`). No direct database file imports. |
| **II. Public API Compatibility & Strict Contract Serialization** | **PASS** | MCP tools declare typed Pydantic models and strict JSON schemas. Upstream status updates invoke `PATCH /api/incidents/{id}/status` to preserve lifecycle rules. Non-blocking async execution used throughout. |
| **III. Strict TypeScript & Static Type Safety** | **PASS** | Monorepo TypeScript packages remain untouched. Python modules maintain 100% type annotations and Pydantic validation across all public boundaries. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | **PASS** | Categorized error taxonomy (`AUTHENTICATION_REQUIRED`, `INSUFFICIENT_SCOPE`, `INVENTORY_MUTATION_REJECTED`, etc.). Plaintext JWTs, passwords, and PII are masked in audit logs. No generic swallowed exceptions. |
| **V. Performance-First Architecture & Core Web Vitals** | **PASS** | Backend/MCP changes have no negative impact on frontend Core Web Vitals. |
| **VI. Test-First Development & Deterministic Verification** | **PASS** | Comprehensive unit and integration test coverage for OAuth authentication, scope enforcement, inventory mutation rejection, lifecycle state transitions, and agent workflow routing. |
| **VII. Vector Database & Qdrant SDK Governance** | **PASS** | Support agent retains encapsulated vector store retrieval through existing `VectorStorePort` without alteration or bypass. |

## Project Structure

### Documentation (this feature)

```text
specs/028-mcp-server-tools/
├── plan.md              # This implementation plan
├── research.md          # Phase 0 architectural & technology decisions
├── data-model.md        # Phase 1 domain entities, lifecycle states, and error taxonomy
├── quickstart.md        # Phase 1 runnable validation scenarios & test guide
├── contracts/           # Phase 1 interface contracts
│   ├── mcp-tools.json   # JSON Schema definitions for exposed MCP tools
│   ├── protected-resource-metadata.json # RFC 9728 OAuth 2.0 Protected Resource Metadata
│   └── audit-log.json   # Structured audit logging event schema
└── tasks.md             # Phase 2 output (/speckit-tasks command - created in next phase)
```

### Source Code Layout

```text
mcps/
└── trackflow-server/                    # Independent MCP Server package
    ├── pyproject.toml                   # uv package configuration
    ├── README.md                        # Documentation & setup instructions
    ├── src/
    │   └── trackflow_server/
    │       ├── __init__.py
    │       ├── main.py                  # Server bootstrap & CLI entrypoint
    │       ├── app.py                   # FastMCP instance & Starlette ASGI assembly
    │       ├── auth/
    │       │   ├── __init__.py
    │       │   ├── middleware.py        # OAuth 2.1 Bearer verification & mcpauth integration
    │       │   ├── metadata.py          # RFC 9728 Protected Resource Metadata endpoint
    │       │   └── scopes.py            # Scope enforcement decorators & permissions
    │       ├── tools/
    │       │   ├── __init__.py
    │       │   ├── incidents.py         # create_incident, query_incidents, transition_incident_status
    │       │   └── inventory.py         # query_inventory (strictly read-only with mutation guard)
    │       ├── clients/
    │       │   ├── __init__.py
    │       │   └── upstream_client.py   # Resilient HTTP client for Incidents & Inventory APIs
    │       ├── logging/
    │       │   ├── __init__.py
    │       │   └── audit.py             # Structured JSON audit logging with PII masking
    │       └── models/
    │           ├── __init__.py
    │           ├── schemas.py           # Pydantic input/output schemas
    │           └── errors.py            # Canonical error codes and exception classes
    └── tests/
        ├── conftest.py                  # Test fixtures & mock token generators
        ├── test_auth.py                 # OAuth 2.1 & scope enforcement tests
        ├── test_incident_tools.py       # Incidents tool execution & lifecycle validation
        ├── test_inventory_tool.py       # Inventory query & mutation rejection tests
        └── test_audit_logging.py        # Audit logging verification

services/api/
├── pyproject.toml                       # Updated with langchain-mcp-adapters
├── application/
│   └── services/
│       └── agent_workflow.py            # Refactored SupportTicketToolPort usage via MCP client
├── infrastructure/
│   └── adapters/
│       ├── mcp_ticket_tool_adapter.py   # New langchain-mcp-adapters client adapter
│       └── support_ticket_tool_adapter.py # Deprecated legacy direct calling adapter
└── presentation/
    └── dependencies.py                  # Injected MCP client adapter into SupportTicketToolPort
```

**Structure Decision**:
- Placed the MCP server as an independent package in `mcps/trackflow-server` complying with the monorepo's `mcps/` modular structure.
- Integrated the MCP client into `services/api` as a port adapter (`mcp_ticket_tool_adapter.py`) implementing `SupportTicketToolPort`, allowing seamless drop-in replacement without altering the LangGraph state machine node wiring, routing edges, or test contracts.

## Complexity Tracking

> No constitution violations detected. All design choices conform strictly to established service boundaries and architecture principles.
