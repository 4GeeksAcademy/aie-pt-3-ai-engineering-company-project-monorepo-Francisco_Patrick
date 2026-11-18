# Tasks: MCP Server - Connecting your Agent to Company Tools

**Input**: Design documents from `/specs/028-mcp-server-tools/`  
**Prerequisites**: [plan.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/plan.md), [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/spec.md), [research.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/research.md), [data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/data-model.md), [contracts/](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/contracts/)

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., [US1], [US2], [US3], [US4])
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and package structure setup for MCP server and agent dependencies.

- [ ] T001 Initialize MCP server package configuration with FastMCP and OAuth dependencies in mcps/trackflow-server/pyproject.toml
- [ ] T002 [P] Initialize package entrypoints and CLI runner in mcps/trackflow-server/src/trackflow_server/__init__.py and mcps/trackflow-server/src/trackflow_server/main.py
- [ ] T003 [P] Add langchain-mcp-adapters dependency to services/api/pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas, models, HTTP client, audit logger, and base server configuration that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete.

- [ ] T004 Implement domain schemas and canonical error models in mcps/trackflow-server/src/trackflow_server/models/schemas.py and mcps/trackflow-server/src/trackflow_server/models/errors.py
- [ ] T005 [P] Implement resilient HTTP client for upstream Incidents and Inventory APIs in mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py
- [ ] T006 [P] Implement structured JSON audit logging with PII and credential masking in mcps/trackflow-server/src/trackflow_server/logging/audit.py
- [ ] T007 [P] Implement FastMCP application initialization and Starlette ASGI routing in mcps/trackflow-server/src/trackflow_server/app.py
- [ ] T008 [P] Setup shared pytest fixtures and mock JWT token helpers in mcps/trackflow-server/tests/conftest.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Secure Incident Ticket Management via Standard Protocol (Priority: P1) 🎯 MVP

**Goal**: Expose operational incident ticket management (`create_incident`, `query_incidents`, `transition_incident_status`) over standard MCP protocol, strictly routing lifecycle status transitions through `PATCH /api/incidents/{id}/status`.

**Independent Test**: Can be independently verified by issuing MCP tool requests with a valid authorization token to create an incident, retrieve its status, and transition its lifecycle status to `in_progress` or `resolved`, confirming the resulting incident state in the central incident repository and rejecting disallowed transitions.

### Tests for User Story 1 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T009 [P] [US1] Create unit tests for incident tools and lifecycle state transitions in mcps/trackflow-server/tests/test_incident_tools.py

### Implementation for User Story 1

- [ ] T010 [US1] Implement create_incident, query_incidents, and transition_incident_status tools delegating to upstream API in mcps/trackflow-server/src/trackflow_server/tools/incidents.py
- [ ] T011 [US1] Register incident tools with FastMCP server instance in mcps/trackflow-server/src/trackflow_server/app.py
- [ ] T012 [US1] Enforce lifecycle state machine validation rules and error mapping for status transitions in mcps/trackflow-server/src/trackflow_server/tools/incidents.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently (MVP Complete).

---

## Phase 4: User Story 2 - Read-Only Inventory Queries with Guaranteed Mutation Protection (Priority: P1)

**Goal**: Expose strictly read-only warehouse stock queries (`query_inventory`) while structurally intercepting and rejecting any write or mutation attempts.

**Independent Test**: Can be independently verified by querying a valid product SKU to verify stock retrieval, followed by attempting write or modification payloads to verify immediate, explainable rejection with zero database alterations.

### Tests for User Story 2 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T013 [P] [US2] Create unit tests for inventory queries and structural mutation rejection in mcps/trackflow-server/tests/test_inventory_tool.py

### Implementation for User Story 2

- [ ] T014 [US2] Implement read-only query_inventory tool delegating to upstream inventory API in mcps/trackflow-server/src/trackflow_server/tools/inventory.py
- [ ] T015 [US2] Register inventory tool with FastMCP server instance in mcps/trackflow-server/src/trackflow_server/app.py
- [ ] T016 [US2] Implement mutation rejection guard intercepting write parameters with INVENTORY_MUTATION_REJECTED in mcps/trackflow-server/src/trackflow_server/tools/inventory.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Standardized Tool Discovery & OAuth Access Control (Priority: P2)

**Goal**: Enforce OAuth 2.1 / OIDC Bearer authentication on all endpoints, publish RFC 9728 Protected Resource Metadata, enforce fine-grained scope permissions per tool, and record structured audit logs.

**Independent Test**: Can be independently verified by connecting without authentication to confirm access is denied, connecting with missing scopes to confirm tool execution is rejected, and connecting with valid credentials to verify full tool discovery metadata.

### Tests for User Story 3 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T017 [P] [US3] Create unit and integration tests for OAuth authentication and scope enforcement in mcps/trackflow-server/tests/test_auth.py
- [ ] T018 [P] [US3] Create unit tests for structured audit logging and PII masking in mcps/trackflow-server/tests/test_audit_logging.py

### Implementation for User Story 3

- [ ] T019 [P] [US3] Implement OAuth 2.1 Bearer verification middleware and mcpauth integration in mcps/trackflow-server/src/trackflow_server/auth/middleware.py
- [ ] T020 [P] [US3] Implement RFC 9728 Protected Resource Metadata endpoint in mcps/trackflow-server/src/trackflow_server/auth/metadata.py
- [ ] T021 [US3] Implement fine-grained scope enforcement decorators and permission matrix in mcps/trackflow-server/src/trackflow_server/auth/scopes.py
- [ ] T022 [US3] Integrate authentication middleware and audit logging middleware into ASGI application in mcps/trackflow-server/src/trackflow_server/app.py
- [ ] T023 [US3] Configure MCP tool discovery metadata and schemas matching contracts in mcps/trackflow-server/src/trackflow_server/app.py

**Checkpoint**: All MCP server endpoints are secured by OAuth 2.1, fine-grained scopes are enforced, and tool discovery metadata is published.

---

## Phase 6: User Story 4 - Support Agent Integration via Standardized Client Adapter (Priority: P2)

**Goal**: Refactor the LangGraph Support Agent in `services/api` to consume the Incidents Manager through the standardized MCP Server via `langchain-mcp-adapters`, decommissioning legacy direct incident calls while preserving RAG routing.

**Independent Test**: Can be independently tested by submitting user support inquiries requiring incident lookups and policy questions to the agent, confirming the agent executes the MCP client adapter, routes correctly to RAG when necessary, and produces verifiable answers without invoking legacy direct tool paths.

### Tests for User Story 4 ⚠️
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T024 [P] [US4] Create unit tests for MCP ticket tool adapter in services/api/tests/unit/test_mcp_ticket_tool_adapter.py
- [ ] T025 [P] [US4] Update integration tests for agent routing and tool execution in services/api/tests/integration/test_agent_routes.py

### Implementation for User Story 4

- [ ] T026 [US4] Implement McpTicketToolAdapter conforming to SupportTicketToolPort using langchain-mcp-adapters in services/api/infrastructure/adapters/mcp_ticket_tool_adapter.py
- [ ] T027 [US4] Inject McpTicketToolAdapter for SupportTicketToolPort in services/api/presentation/dependencies.py
- [ ] T028 [US4] Refactor agent workflow service to consume MCP adapter and decommission legacy direct incident calling node in services/api/application/services/agent_workflow.py
- [ ] T029 [US4] Deprecate legacy direct support ticket tool adapter in services/api/infrastructure/adapters/support_ticket_tool_adapter.py

**Checkpoint**: All user stories should now be independently functional and integrated end-to-end.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, end-to-end scenario verification, type integrity, and test suite execution.

- [ ] T030 [P] Add README and developer documentation in mcps/trackflow-server/README.md
- [ ] T031 Run quickstart.md validation scenarios against running MCP server and agent in specs/028-mcp-server-tools/quickstart.md
- [ ] T032 Verify static type integrity, linting, and backend test suite execution across mcps/trackflow-server and services/api

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1: Setup
     │
     ▼
Phase 2: Foundational (Blocking Prerequisites)
     │
     ├──────────────────────┬──────────────────────┐
     ▼                      ▼                      ▼
Phase 3: US1 (P1)      Phase 4: US2 (P1)      Phase 5: US3 (P2)
     │                      │                      │
     └──────────────────────┼──────────────────────┘
                            ▼
                       Phase 6: US4 (P2)
                            │
                            ▼
                       Phase 7: Polish
```

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) - BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) completion.
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) completion. Can run in parallel with US1.
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) completion. Adds security/discovery wrappers around registered tools.
- **User Story 4 (Phase 6)**: Depends on US1 (Phase 3) and US3 (Phase 5) being functional so the agent can invoke MCP incident tools via client adapter.
- **Polish (Phase 7)**: Depends on all user stories (Phases 3-6) being complete.

---

## Parallel Execution Opportunities

### Phase 1 (Setup)
- `T002` (CLI runner) and `T003` (agent dependencies) can execute concurrently once `T001` initializes `pyproject.toml`.

### Phase 2 (Foundational)
- `T005` (upstream client), `T006` (audit logging), `T007` (FastMCP app skeleton), and `T008` (test fixtures) can all execute in parallel once `T004` (schemas & errors) is defined.

### Phase 3 (User Story 1) & Phase 4 (User Story 2)
- Tests `T009` and `T013` can be written in parallel.
- US1 (`T010`-`T012`) and US2 (`T014`-`T016`) touch completely distinct tool files (`tools/incidents.py` vs `tools/inventory.py`) and can execute concurrently.

### Phase 5 (User Story 3)
- Tests `T017` and `T018` can execute in parallel.
- Auth middleware (`T019`) and metadata endpoint (`T020`) can be authored in parallel before assembling in `T022`.

### Phase 6 (User Story 4)
- Unit tests (`T024`) and integration tests (`T025`) can be drafted in parallel before implementing adapter `T026`.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete **Phase 1: Setup** (`T001`-`T003`).
2. Complete **Phase 2: Foundational** (`T004`-`T008`).
3. Complete **Phase 3: User Story 1** (`T009`-`T012`).
4. **STOP and VALIDATE**: Run `pytest mcps/trackflow-server/tests/test_incident_tools.py` to confirm incident ticket creation, querying, and lifecycle transitions work over standard MCP.
5. Demonstrate working MVP.

### Incremental Delivery

1. Setup + Foundational → Core infrastructure ready.
2. User Story 1 (Incident Tools) → MVP operational.
3. User Story 2 (Read-Only Inventory) → Warehouse stock queries operational with mutation rejection guardrail.
4. User Story 3 (OAuth & Discovery) → Enterprise security boundary, RFC 9728 metadata, and audit logging active.
5. User Story 4 (Agent Integration) → LangGraph Support Agent seamlessly consuming tools via MCP adapter.
6. Polish → Verification against all quickstart validation scenarios and test suite passes.
