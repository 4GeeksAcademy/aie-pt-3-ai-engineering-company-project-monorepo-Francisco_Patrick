# Feature Specification: MCP Server - Connecting your Agent to Company Tools

**Feature Branch**: `028-mcp-server-tools`

**Created**: 2026-11-18

**Status**: Ready for Planning

**Input**: User description: "Decouple the current agent tools to build an independent, standardized MCP Server protected by OAuth, allowing its reuse by multiple internal and external clients. This server will expose the comprehensive ticket management of the Incidents Manager and strictly read-only access to the inventory, ensuring the principle of least privilege and providing clear discovery metadata so that any external agent can understand its capabilities without requiring human context. In parallel, the objective requires refactoring the original agent to replace its direct calls with the consumption of this new server (using langchain-mcp-adapters), keeping the routing with the RAG system intact. The implementation must resolve key architectural decisions: the choice of transport (stdio vs. HTTP) according to remote consumption, and the structural permissions design that defaults to rejecting any modification attempt on inventory data."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure Incident Ticket Management via Standard Protocol (Priority: P1)

Internal and external client agents need to manage operational incident tickets (creating new incidents, querying incident details/status, and transitioning ticket lifecycle status) through a standardized, protocol-driven interface rather than custom, tightly coupled internal service calls. The client connects to the server with an authorized security token, performs ticket operations, and receives structured, deterministic responses reflecting the live state in the company's central Incidents Manager.

**Why this priority**: Incident ticketing is the core operational capability needed by automated support agents and customer-facing workflows. Exposing this functionality through a standardized, secure protocol enables multiple automated clients to coordinate incident resolution safely and consistently.

**Independent Test**: Can be independently verified by issuing protocol tool requests with a valid authorization token to create an incident, retrieve its status, and transition its lifecycle status to `in_progress` or `resolved`, confirming the resulting incident state in the central incident repository.

**Acceptance Scenarios**:

1. **Given** an authenticated client with valid ticket management permissions, **When** the client invokes ticket creation with required attributes (title, description, category, origin, branch), **Then** a new incident is created in the central incident registry in `open` status, returning the assigned incident identifier and full record details.
2. **Given** an authenticated client, **When** the client queries tickets by identifier or filter criteria (status, origin, category, branch), **Then** all matching incident records conforming to the company's domain structure are returned.
3. **Given** an existing incident in `open` status, **When** the client submits a status transition to `in_progress`, **Then** the status change is validated against lifecycle state rules, executed through the dedicated lifecycle endpoint, and the updated record is returned.
4. **Given** an authenticated client, **When** the client attempts an invalid status transition (e.g., transitioning a `discarded` incident directly to `resolved`), **Then** the request is rejected with a distinct domain error explaining the disallowed lifecycle transition without altering state.

---

### User Story 2 - Read-Only Inventory Queries with Guaranteed Mutation Protection (Priority: P1)

Client agents and automated workflows need real-time visibility into warehouse stock levels and product catalog availability without having permission to alter inventory counts or register warehouse shipments. When a client requests stock information, the server provides accurate stock projections. When any client attempts to submit write, update, adjustment, or deletion operations against inventory, the server explicitly rejects the operation.

**Why this priority**: Protecting warehouse inventory accuracy is a non-negotiable security and governance requirement. Read access is essential for customer support inquiries, while strictly rejecting any mutation attempts prevents accidental stock corruption, data tampering, and inventory discrepancies.

**Independent Test**: Can be independently tested by querying a valid product SKU to verify accurate stock level retrieval, followed by attempting write or modification actions to verify immediate, explainable rejection with zero database alterations.

**Acceptance Scenarios**:

1. **Given** an authenticated client with inventory read permissions, **When** the client queries stock by product identifier or SKU, **Then** the server returns the product details including current stock, warehouse location, and low-stock alerts.
2. **Given** an authenticated client, **When** the client attempts any modification, write operation, stock adjustment, or creation through the inventory capability, **Then** the server explicitly rejects the operation with a distinct permission rejection code explaining that inventory access is strictly read-only.
3. **Given** a query for a non-existent product SKU or identifier, **When** the inventory query is processed, **Then** the server returns a structured not-found response without failing unexpectedly.

---

### User Story 3 - Standardized Tool Discovery & OAuth Access Control (Priority: P2)

External and internal client applications need to inspect available tools dynamically to understand input parameters, required data types, descriptions, and operational constraints without human intervention or prior manual documentation. Furthermore, unauthorized or improperly scoped clients must be barred from listing or running any tool.

**Why this priority**: Autonomous agents depend on dynamic protocol discovery metadata to select tools and construct valid parameters automatically. Enforcing OAuth 2.1 / OIDC protection at the resource boundary ensures company tools are never exposed to unauthenticated or unauthorized parties.

**Independent Test**: Can be verified by connecting an inspector client without authentication to confirm access is denied, and subsequently connecting with a valid token to verify complete discovery metadata containing parameter schemas, tool names, and descriptive guidelines.

**Acceptance Scenarios**:

1. **Given** an unauthenticated client request to discover or execute tools, **When** the request arrives at the server, **Then** access is denied with an explicit authentication challenge before any tool logic or discovery metadata is evaluated.
2. **Given** an authenticated client presenting a token lacking required scopes for a specific tool, **When** the client attempts to invoke that tool, **Then** execution is denied with an authorization failure detailing missing required scopes.
3. **Given** an authorized client requesting tool capabilities via standard protocol discovery, **When** the server responds, **Then** each tool provides clear descriptions, typed input/output schemas matching existing company entity models, and clear documentation of constraints.
4. **Given** any tool execution request, **When** the request is processed, **Then** a structured log entry is recorded capturing client identity, tool name, sanitized execution parameters, outcome status, and duration.

---

### User Story 4 - Support Agent Integration via Standardized Client Adapter (Priority: P2)

The company's automated support agent needs to consume the Incidents Manager through the standardized protocol client rather than making direct internal service calls or raw HTTP requests. The agent's existing multi-source routing (intake -> operational tools -> knowledge retrieval / RAG -> response generation -> fallback) must continue functioning smoothly without dual or bypass pathways.

**Why this priority**: Decouples the agent workflow from monolithic internal services, ensuring that both internal agents and external automated clients consume operational tools through the same secure, audited protocol contract.

**Independent Test**: Can be independently tested by submitting user support inquiries requiring incident lookups and policy questions to the agent, confirming the agent executes the protocol client adapter node, routes correctly to RAG when necessary, and produces verifiable answers without invoking legacy direct tool paths.

**Acceptance Scenarios**:

1. **Given** a customer query referencing an incident ticket identifier, **When** the support agent processes the inquiry, **Then** the agent dispatches the tool call through the protocol client adapter and incorporates the resulting incident data into the final response.
2. **Given** a multi-part inquiry covering both an incident status and a company policy, **When** the agent workflow executes, **Then** it queries the protocol ticket tool, progresses along canonical routing to RAG knowledge retrieval, and synthesizes a grounded answer citing both sources.
3. **Given** the updated agent configuration, **When** the migration is complete, **Then** the legacy direct incident tool implementation is removed or disabled, ensuring a single unified path to incident operations via the protocol client.

---

### Edge Cases

- **Token Expiration or Revocation**: If a client's access token expires mid-session, subsequent tool calls must be rejected with an explicit authentication expiration code, prompting token renewal without crashing the connection.
- **Upstream Service Latency & Downtime**: When the underlying Incidents Manager or Inventory database is slow or unreachable, the server must enforce explicit timeouts and return structured upstream unavailable responses rather than hanging indefinitely.
- **Conflicting or Malformed Query Filters**: When queries provide contradictory parameters (e.g., valid ticket identifier combined with mismatched status filters), the server returns a clean not-found or validation error without throwing uncaught server errors.
- **Disallowed Lifecycle Transitions**: When updating an incident status, any transition violating business lifecycle rules (such as transitioning `resolved` back to `open` or modifying a `discarded` incident) is rejected by the lifecycle endpoint and passed to the caller with clear explanatory messaging.
- **Remote Transport Connectivity**: When consumed remotely via public URLs (such as forwarded cloud environment ports), the server must serve metadata and tool executions over a remote-capable transport without host header or proxy corruption.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The MCP Server MUST be implemented in Python located within the `mcps/` directory of the monorepo.
- **FR-002**: The MCP Server MUST implement standard Model Context Protocol (MCP) tool discovery, exposing descriptive tool names, markdown docstrings, and strict JSON schemas for input parameters.
- **FR-003**: The MCP Server MUST enforce OAuth 2.1 / OIDC authentication as an MCP resource server using `mcpauth`, validating bearer JWT tokens on all tool discovery and invocation endpoints.
- **FR-004**: The MCP Server MUST publish Protected Resource Metadata allowing clients to locate the authorization server and required scopes according to MCP specifications.
- **FR-005**: The MCP Server MUST enforce fine-grained authorization scopes (least privilege) per tool, rejecting requests from clients that lack required scopes with distinct authorization error codes.
- **FR-006**: The MCP Server MUST expose a ticket management tool that supports creating new incidents, querying incident status and details, and transitioning incident status.
- **FR-007**: Ticket status transitions MUST be routed strictly through the Incidents Manager lifecycle endpoint (`PATCH /api/incidents/{id}/status`) to guarantee lifecycle state machine validation.
- **FR-008**: Field names, identifiers, and enum values used in the ticket management tool MUST conform to the existing Incidents Manager domain model (`id`, `title`, `description`, `status`, `category`, `origin`, `branch`, `created_at`, `updated_at`).
- **FR-009**: The MCP Server MUST expose an inventory query tool that provides product stock levels, threshold warnings, and warehouse locations.
- **FR-010**: The inventory tool MUST enforce a strictly read-only security boundary: any parameter, action, or payload attempting to create, update, adjust, or delete inventory records MUST be explicitly rejected with a dedicated error code and explanation.
- **FR-011**: The MCP Server MUST emit structured audit log records for every tool invocation, detailing client identity, tool name, input arguments (with sensitive data masked), execution status, and elapsed latency.
- **FR-012**: Errors returned across the MCP interface MUST be distinctly categorized (authentication failure, insufficient permissions, input validation error, business logic rejection, or upstream dependency timeout) rather than generic error strings.
- **FR-013**: The LangGraph support agent in `services/api/application/services/agent_workflow.py` MUST be refactored to consume the Incidents Manager through the MCP Server using `langchain-mcp-adapters`.
- **FR-014**: The previous direct internal/HTTP calling node in the support agent MUST be decommissioned so that only a single path (the MCP client) exists for incident operations.
- **FR-015**: The agent's existing multi-source routing, parameter extraction, and coordination between operational tools and RAG knowledge retrieval MUST remain fully operational post-migration.
- **FR-016**: Dependencies required for the MCP Server and agent integration (e.g., `fastmcp`, `mcpauth`, `langchain-mcp-adapters`) MUST be managed strictly with `uv add` without manual unmanaged package installations.

### Key Entities

- **MCP Tool Definition**: Represents an exposed capability on the MCP Server, containing tool name, description, JSON schema for input arguments, output schema, and required authorization scopes.
- **Incident Ticket**: The core domain entity representing an operational issue in TrackFlow, containing `id` (e.g. `INC-001` or UUID), `title`, `description`, `status` (`open`, `in_progress`, `resolved`, `discarded`), `category`, `origin`, `branch`, and timestamps.
- **Inventory Product Record**: The domain entity representing physical stock, containing `id`, `sku`, `name`, `description`, `stock`, `min_threshold`, `is_low_stock`, and `warehouse_id`.
- **OAuth Security Context**: The validated authentication context extracted from the client's bearer token, containing client ID, subject identifier, issuer, expiration, and granted scope list.
- **Audit Log Entry**: Traceability record generated per tool execution, containing timestamp, trace ID, client identity, target tool, request arguments, outcome (`success`, `rejected`, `error`), and execution duration in milliseconds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of unauthenticated or expired client requests to list or invoke tools are rejected with an explicit authentication challenge before executing any tool logic.
- **SC-002**: 100% of write or mutation attempts on the inventory tool are blocked with an explicit, explainable rejection response, resulting in exactly zero database alterations.
- **SC-003**: External agents and validation tools can discover all tools, parameter types, and descriptions solely through protocol discovery without human intervention or supplementary documentation.
- **SC-004**: 100% of incident status updates made through the server comply with the lifecycle state machine of the Incidents Manager, correctly invoking the lifecycle status endpoint.
- **SC-005**: 100% of tool invocations produce structured audit logs containing client identity, tool name, sanitized parameters, outcome, and execution latency.
- **SC-006**: The automated support agent completes incident and inventory inquiries exclusively via the standardized protocol client, with zero invocations to deprecated direct tool adapters.
- **SC-007**: Multi-source support agent queries involving both ticket tools and knowledge retrieval achieve successful end-to-end response generation without regression in routing accuracy or response relevance.
- **SC-008**: The server successfully validates against an interactive protocol client interface when accessed through a publicly accessible remote endpoint.

## Assumptions

- The Incidents Manager backend (`services/api/presentation/api/v1/incidents.py`) and the Inventory service (`services/api/presentation/api/v1/inventory.py`) are operational and represent the single source of truth for their respective domains.
- An OAuth 2.1 / OIDC compatible provider or mock token issuer is available or configurable for token issuance during development, testing, and Playground validation.
- Remote validation via MCP Playground can utilize publicly forwarded ports in GitHub Codespaces or equivalent tunneling tools.
- Remote transport requirements are satisfied by an HTTP/SSE-capable transport provided by the MCP framework (such as FastMCP with SSE/HTTP transport) to allow remote client consumption.
- Python dependencies are strictly resolved and locked using `uv` in accordance with repository standards.
