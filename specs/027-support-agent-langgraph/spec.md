# Feature Specification: Support Agent with LangGraph — Explicit Reasoning & Operational Tools Outside the RAG

**Feature Branch**: `feature/langgraph-external-tools`

**Created**: 2026-11-17

**Updated**: 2026-11-18

**Status**: Draft

**Input**: User description: "Update Spec `027-support-agent-langgraph`: Tools Outside the RAG. Overview: Evolve the current support agent, which uses RAG for static policy information inside an explicit compiled state graph, by equipping it with single-responsibility read-only operational tools to access real-time data from the existing Incident Manager and Inventory Manager. The agent must autonomously decide based on the user's inquiry whether to query the static knowledge base (RAG), invoke a real-time operational tool (support ticket query or inventory stock query), or combine both, while enforcing explicit numerical timeouts, honest non-hallucinating fallback routes on tool failure or missing records, full execution trace visibility of data sources and invocation order, and automated routing and fallback evaluation tests."

## Clarifications

### Session 2026-11-18

- Q: When a hybrid inquiry requires multiple data sources (for example, both a live operational tool and static policy retrieval), in what fixed order should the workflow execute those stages? → A: Operational tools first (`ticket_tool` → `inventory_tool`), then static retrieval (`rag`), then synthesis/fallback.
- Q: When a hybrid inquiry combines a live operational tool lookup and a static policy question, and the operational tool fails, times out, or finds no matching record while static policy retrieval succeeds, how should the workflow respond? → A: Graceful partial answer: record the tool fallback, still execute `rag`, and return the verified policy answer alongside an honest inability-to-confirm notice for the tool part.
- Q: When the Support Ticket Tool or Inventory Stock Query Tool executes a filter-based query that matches multiple records (for example, all open incidents or matching products), what maximum number of records should a single tool call return into the agent state? → A: Cap at 20 records per tool call (most recent/relevant first) plus a `total_matched` count in the tool output.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explicit, Traceable Reasoning Flow for Customer Inquiries (Priority: P1)

As a TrackFlow Support Coordinator or Commercial Operations Lead,
I want customer inquiries to be processed through an explicit state machine with distinct stages for input intake, intent routing, context retrieval, tool execution, and response synthesis,
So that every decision and data transformation is transparent, audit-ready, and independently verifiable rather than hidden in a black-box execution.

**Why this priority**:
Monolithic, black-box pipelines obscure failure points, making it impossible to determine whether an erroneous answer resulted from malformed questions, misrouted intents, missing retrieval context, external tool faults, or generation hallucinations. Making the flow explicit as a compiled state graph is the foundation for trusting automated agents in production.

**Independent Test**:
Can be fully verified by submitting a standard operational policy question (e.g., standard return policy or storage rates) and asserting that the system executes the single-responsibility intake and routing stage, followed by the knowledge retrieval stage, followed by the answer generation stage, producing an accurate grounded response with citations and recording each distinct stage.

**Acceptance Scenarios**:

1. **Given** an inquiry regarding TrackFlow's standard return policy ("What is TrackFlow's standard return window?"),
   **When** the agent workflow executes,
   **Then** the inquiry enters the question intake stage, routes to the static knowledge retrieval stage which fetches relevant policy chunks from verified company documentation, transitions to the generation stage with the retrieved context, and returns a verified answer stating the 30-day return policy along with source citations without invoking live operational tools.
2. **Given** an inquiry about warehouse storage rates in Zaragoza and Los Angeles,
   **When** the agent processes the request,
   **Then** retrieval produces matching storage pricing sections before generation is called, ensuring the generation stage does not re-invoke retrieval and remains strictly bounded by the retrieved context.

---

### User Story 2 - Autonomous Routing & Live Support Ticket Queries Outside the Knowledge Base (Priority: P1)

As a Customer Support Specialist or Operations Manager,
I want the support agent to automatically distinguish between static company policy questions and real-time support ticket inquiries—and query live incident data via a dedicated, read-only support ticket tool,
So that users receive accurate, up-to-the-minute incident statuses, categories, origins, and timestamps directly from the incident management system instead of outdated or fabricated responses.

**Why this priority**:
Static knowledge bases cannot answer live operational questions about open support tickets or incident statuses. Separating stable documentation from live operational tool calls prevents stale answers and enables the agent to resolve real-time ticket lookups autonomously without requiring the user to specify which backend source to query.

**Independent Test**:
Can be fully verified by submitting a natural-language question asking for the status or details of an existing incident ticket (or filtered list of incidents by status, category, origin, or branch) and verifying that the agent routes autonomously to the support ticket tool, reads live data from the incident management service, and returns accurate ticket fields in its response.

**Acceptance Scenarios**:

1. **Given** a natural-language inquiry asking about a specific existing support ticket (e.g., "What is the current status and category of ticket INC-001?"),
   **When** the agent evaluates the inquiry without any explicit source hint from the user,
   **Then** the routing logic directs execution to the read-only support ticket query tool, retrieves the real ticket record (status, category, origin, branch, creation/update dates) from the live incident management system, and synthesizes an accurate answer reflecting those exact live attributes without querying static policy documentation.
2. **Given** a natural-language inquiry asking to inspect live tickets matching operational filters (e.g., "Are there any open critical incidents originating from warehouse operations?"),
   **When** the agent executes,
   **Then** the support ticket tool queries the live incident data store with the corresponding read-only filters and returns a summary grounded strictly in the live incident records.
3. **Given** a hybrid inquiry combining live ticket data and static company policy (e.g., "What is the status of ticket INC-001, and what is our standard return policy window for damaged goods?"),
   **When** the agent processes the inquiry,
   **Then** the workflow invokes both the support ticket tool and the static knowledge retrieval node in an explicit, traceable sequence and synthesizes a unified response grounded in both sources.

---

### User Story 3 - Explicit Tool Timeouts and Honest Error Recovery Fallback Routes (Priority: P1)

As a Reliability Engineer and Customer Support Lead,
I want every operational tool call to enforce an explicit numerical timeout and transition to a controlled fallback route whenever a service times out, becomes unreachable, or reports that a requested ticket or product does not exist,
So that the agent workflow never hangs indefinitely and always replies honestly without inventing ticket statuses or stock levels.

**Why this priority**:
Live operational services can experience latency spikes, downtime, or missing record lookups. If an external tool call hangs or fails unhandled, it either blocks the entire support system or tempts the language model to hallucinate plausible-sounding statuses. Deterministic timeouts and explicit error recovery routes guarantee resilience and factual honesty.

**Independent Test**:
Can be fully verified by querying a non-existent ticket identifier and by simulating a tool timeout or service unavailability condition, asserting that execution completes within the timeout bound, transitions to the fallback route, and replies with an honest inability-to-confirm message without invented data.

**Acceptance Scenarios**:

1. **Given** an inquiry referencing a support ticket identifier that does not exist in the incident management system (e.g., "What is the status of ticket INC-999999?"),
   **When** the support ticket tool executes and finds no matching record,
   **Then** the workflow transitions via the fallback route and responds honestly that the ticket could not be found or confirmed, never inventing a status, category, or date.
2. **Given** an incident or inventory service call that exceeds the configured numerical timeout (e.g., 4 seconds) or raises a connection/service error,
   **When** the tool node catches the timeout or operational exception,
   **Then** the workflow does not hang or crash; it transitions to the explicit error recovery fallback route and replies honestly (such as "I couldn't confirm the status of that ticket right now") while recording the fallback path in the run trace.

---

### User Story 4 - Live Inventory Stock Query via Single-Responsibility Tool (Priority: P2)

As a Warehouse Coordinator or Account Representative,
I want the support agent to autonomously answer real-time product stock and availability questions using a dedicated, read-only inventory query tool separate from the support ticket tool,
So that operators can verify live product stock levels, SKUs, and low-stock indicators alongside policy and incident inquiries while preserving strict single-responsibility boundaries across tools.

**Why this priority**:
TrackFlow manages live warehouse inventory in addition to support incidents. Providing a dedicated, typed, read-only inventory query tool empowers the support agent to answer real-time stock inquiries without conflating ticket lookup logic and inventory lookup logic inside a single multi-purpose tool.

**Independent Test**:
Can be fully verified by asking the agent for current stock availability of an existing product or SKU (and a missing SKU or unavailable inventory service) and confirming that the agent invokes the standalone inventory query tool—never the ticket tool or static RAG—and enforces the same timeout and honest fallback rules.

**Acceptance Scenarios**:

1. **Given** a natural-language question about current warehouse stock for a product (e.g., "How many units of SKU TF-1001 are currently in stock?"),
   **When** the agent routes the inquiry,
   **Then** it selects the dedicated read-only inventory query tool, queries the live inventory management data store, and reports the authentic stock quantity and threshold status.
2. **Given** a query for a product SKU that does not exist or when the inventory service times out,
   **When** the inventory tool executes,
   **Then** it enforces the explicit numerical timeout and routes to the honest fallback response stating that stock availability for that product could not be confirmed right now, without fabricating inventory numbers.

---

### User Story 5 - Conditional Branching and Honest Policy Refusal (Priority: P2)

As a Commercial Governance Lead,
I want the agent workflow to evaluate dynamic output conditions between steps and branch conditionally,
So that empty questions immediately halt without executing costly retrieval or tool calls, and policy queries lacking verified documentation route to an honest refusal message instead of forcing generation on ungrounded context.

**Why this priority**:
Preventing hallucinations and wasted compute on unsupported topics is a core business requirement. Explicit conditional branching guarantees that the agent never attempts to generate policy answers when no supporting context exists above the calibrated confidence threshold.

**Independent Test**:
Can be fully verified by submitting an empty/whitespace query and an out-of-scope policy query (e.g., pharmaceutical refrigeration policies), verifying that the workflow terminates early on empty input and conditionally routes to an honest refusal stage when similarity thresholds are not met and no operational tool applies.

**Acceptance Scenarios**:

1. **Given** a blank or whitespace-only inquiry string,
   **When** the intake stage evaluates the inquiry,
   **Then** the workflow immediately halts via a conditional edge without invoking vector retrieval, operational tools, or language models, returning a clear validation failure.
2. **Given** a query concerning policies absent from TrackFlow's knowledge base and unrelated to live tickets or inventory (e.g., temperature-controlled pharmaceutical storage regulations),
   **When** the retrieval stage executes and finds zero document chunks satisfying the calibrated similarity threshold,
   **Then** a conditional edge routes execution to a dedicated refusal stage rather than the generation stage, returning an honest standard refusal.

---

### User Story 6 - Queryable Multi-Source Execution Tracing and State Checkpointing (Priority: P2)

As a Tech Lead and AI Systems Engineer,
I want every execution run to record a structured, queryable trace of node visitations, data sources consulted (static knowledge base, support ticket tool, inventory tool, or a combination), exact invocation sequence, fallback activations, and persisted state checkpoints,
So that production runs can be audited post-hoc to verify which source(s) answered a question and in what order.

**Why this priority**:
As the agent expands from single-source static retrieval to multi-source orchestration (RAG + external operational tools + fallback recovery), observability must clearly distinguish whether an answer came from static documentation, a live tool call, both, or an error fallback route.

**Independent Test**:
Can be fully verified by executing policy-only, ticket-tool-only, inventory-tool-only, hybrid (RAG + tool), and tool-fallback inquiries, retrieving each run's trace record, and asserting that the trace explicitly lists the ordered sequence of visited nodes, the distinct sources used, per-step latencies, and checkpoint identifiers.

**Acceptance Scenarios**:

1. **Given** a completed agent run that used a live tool, static retrieval, or both,
   **When** an engineer or automated test inspects the run trace,
   **Then** the trace clearly distinguishes which source(s) were consulted (`rag`, `ticket_tool`, `inventory_tool`, or combinations thereof), the exact node execution order, per-node latency, and tool call outcome status.
2. **Given** a multi-step execution across routing, tool invocation, retrieval, or fallback nodes,
   **When** state transitions occur,
   **Then** a state checkpoint is persisted with a unique thread/run identifier allowing point-in-time state inspection.

---

### User Story 7 - Automated Evaluation Suite for Routing, Grounding, and Fallback Gates (Priority: P3)

As a Quality Assurance and Release Engineer,
I want an automated evaluation test suite runnable via a single command that validates autonomous routing between RAG and operational tools, knowledge grounding, and fallback recovery when a live tool or resource fails,
So that regressions in intent routing, tool contracts, or fallback honesty are caught automatically before deployment.

**Why this priority**:
Adding live operational tools introduces routing ambiguity risks (e.g., accidentally calling RAG for a live ticket ID or calling the ticket tool for a general return policy question). Automated evaluation tests verify that the agent selects the right source autonomously and recovers honestly on failure.

**Independent Test**:
Can be fully verified by running the automated evaluation test suite (`pytest tests/pipelines/`), confirming that existing RAG evaluations pass alongside at least two new routing evaluations (one resolved exclusively via an operational tool, one resolved exclusively via RAG) plus an evaluation verifying honest fallback behavior when an operational service is unavailable or a ticket is missing.

**Acceptance Scenarios**:

1. **Given** an evaluation test with a live support ticket inquiry (e.g., querying the status of a specific incident ticket),
   **When** the evaluation runs,
   **Then** the trace confirms that the agent routed to the support ticket tool (and did not rely on static RAG to fabricate ticket status) and returned an answer matching the live incident record.
2. **Given** an evaluation test with a static company policy inquiry (e.g., standard return window or warehouse storage policy),
   **When** the evaluation runs,
   **Then** the trace confirms that the agent resolved the question using static knowledge retrieval (RAG) without invoking the support ticket or inventory operational tools.
3. **Given** an evaluation test simulating an unavailable incident service or non-existent ticket lookup,
   **When** the evaluation runs,
   **Then** the trace confirms traversal of the fallback route and asserts that the final response honestly reports inability to confirm the ticket status without hallucinating values.

---

### User Story 8 - Zero-Leakage API Integration Endpoint (Priority: P4)

As a Frontend or External Service Client,
I want to query the support agent through a standardized HTTP REST endpoint that invokes the compiled workflow and shields internal operational mechanics,
So that client applications receive clean structured responses (including trace and source metadata) and sanitized error messages even when internal nodes or external services encounter faults.

**Why this priority**:
In accordance with the TrackFlow Constitution, public APIs must present strict response schemas, execute asynchronously without blocking the event loop, and never leak raw stack traces, internal file paths, or credentials across HTTP boundaries.

**Independent Test**:
Can be fully verified by dispatching valid policy queries, live ticket queries, and simulated fault requests to the agent endpoint, confirming HTTP 200 with structured response bodies for normal and gracefully degraded tool fallback runs, and sanitized error payloads (zero stack traces) for unhandled system faults.

**Acceptance Scenarios**:

1. **Given** a valid JSON request posted to the agent endpoint (`POST /agent/query` or `/api/v1/agent/query`),
   **When** the endpoint invokes the compiled graph for either a policy question or a live operational tool question,
   **Then** it returns HTTP 200 with the synthesized answer, citations/tool metadata, node execution sequence, and queryable trace identifier.
2. **Given** an unhandled internal exception within the workflow infrastructure,
   **When** the endpoint processes the failure,
   **Then** it returns a sanitized user-facing error response without exposing raw stack traces, code lines, or configuration secrets.

---

### Edge Cases

- **Empty or Whitespace Queries**: Inquiries containing only spaces, tabs, or newlines must not trigger vector search embeddings or operational tool calls; they must conditionally terminate at intake with an informative validation status.
- **Non-Existent Ticket ID or Product SKU**: When a user asks for a ticket ID (e.g., `INC-404`) or product SKU that does not exist in the real operational database, the tool must return a structured not-found result that routes to the honest fallback response rather than raising an unhandled crash or fabricating data.
- **Operational Service Timeout (Latency Exceeding Threshold)**: When the incident manager or inventory manager fails to respond within the explicit numerical timeout window (e.g., 4.0 seconds), the tool call must abort cleanly and route to the controlled fallback response without hanging the graph runner.
- **Operational Service Connection Failure or HTTP 5xx**: When the incident or inventory service is offline or returns an internal error, the graph must catch the failure, record the tool failure in the trace, and transition to the fallback node to deliver an honest response.
- **Ambiguous or Multi-Intent Queries**: When a user inquiry asks both about a live operational record (ticket or stock level) and a static company policy in the same question, the routing mechanism must execute the selected stages in the canonical order (`ticket_tool` → `inventory_tool` → `rag`) before synthesizing the final response; if an operational tool fails, times out, or finds no record during a hybrid inquiry, the workflow records the tool fallback, continues to `rag`, and returns the verified policy answer alongside an honest inability-to-confirm notice for the unconfirmed operational part.
- **Attempted Write/Mutation Prompt Injection**: If a user prompts the agent to create, modify, close, or delete an incident ticket or update product stock quantities, the agent must strictly refuse or restrict execution to read-only queries because operational tools are strictly read-only by contract.
- **Out-of-Distribution / Zero-Hit Policy Queries**: Queries unrelated to operational tools and having semantic similarity below the calibrated threshold (0.62) in the knowledge base must branch to a dedicated refusal node rather than generating ungrounded answers.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Core Graph & Static Knowledge Retrieval (Part 1 Foundation)

- **FR-001**: The system MUST define an explicit, minimal state schema containing the user query, routing decision metadata, retrieved static context chunks, structured operational tool outputs, fallback/refusal indicators, synthesized answer, and execution trace metadata, excluding unbounded raw conversational history.
- **FR-002**: The system MUST implement single-responsibility workflow nodes with clear boundaries: question intake/routing, static context retrieval (RAG), support ticket query tool execution, inventory stock query tool execution, tool fallback/recovery handling, policy refusal handling, and answer generation.
- **FR-003**: The static context retrieval node MUST reuse existing retrieval and embedding services from the codebase without duplicating vector search or embedding logic.
- **FR-004**: The answer generation node MUST synthesize responses strictly from pre-retrieved static context chunks and/or structured tool outputs present in the state, and MUST NOT invoke retrieval or external operational services directly.
- **FR-005**: The workflow MUST implement explicit conditional edges that evaluate state outputs to route inquiries across intake validation, tool invocation(s), static knowledge retrieval, tool failure fallback, policy refusal, and answer generation.
- **FR-006**: The workflow MUST be explicitly compiled prior to execution, raising deterministic compilation errors upon structural defects (unconnected nodes, invalid transition targets, or mismatched state schemas).
- **FR-007**: The workflow MUST incorporate state checkpointing at meaningful node transitions, persisting execution state linked to a verifiable thread or run identifier.
- **FR-008**: Every execution of the agent workflow MUST produce a queryable trace capturing the ordered node visitation sequence, data sources consulted, execution timestamps/latencies per step, and input/output state summaries.
- **FR-009**: The system MUST provide an automated evaluation suite in `tests/pipelines/` runnable via a single test command.
- **FR-010**: The evaluation suite MUST include verifiable test cases that inspect trace ordering, conditional branching, tool routing, fallback handling, and output correctness.
- **FR-011**: At least one evaluation test case MUST assert that policy answers remain grounded in TrackFlow's verified briefing documentation (`docs/rag/trackflow-BRIEFING.en` or `docs/company-knowledge-base/`).
- **FR-012**: All pre-existing RAG and pipeline regression tests MUST continue to pass alongside the expanded agent evaluations.
- **FR-013**: The system MUST expose the compiled agent workflow via a dedicated HTTP REST endpoint (`POST /agent/query` and `/api/v1/agent/query`) that delegates entirely to the workflow without embedding business logic in the route handler.
- **FR-014**: The API endpoint MUST handle runtime workflow failures defensively, returning sanitized error responses while strictly preventing raw stack traces or internal system paths from leaking to consumers.
- **FR-015**: The agent endpoint handler MUST execute asynchronously without blocking the server event loop, adhering to monorepo architectural standards.

#### Real-Time Operational Tools & Autonomous Routing (Part 2 Expansion)

- **FR-016**: The system MUST define a strict, typed input and output contract for the **Support Ticket Query Tool**, accepting a specific ticket identifier (`ticket_id`) or search filter criteria (`status`, `category`, `origin`, `branch`) and returning up to 20 matching typed incident records (ordered most recent first) containing identical domain attributes exposed by the Incident Manager (`id`, `title`, `description`, `status`, `category`, `origin`, `branch`, `created_at`, `updated_at`), a `total_matched` count, and call status metadata.
- **FR-017**: The Support Ticket Query Tool MUST read real operational data from the existing TrackFlow Incident Manager (via its service/repository layer in-process or via HTTP to `GET /api/incidents` and `GET /api/incidents/{id}`) and MUST NEVER use mocked, hardcoded, or parallel fake datasets in application code.
- **FR-018**: The system MUST define a strict, typed input and output contract for the **Inventory Stock Query Tool**, accepting a product identifier (`product_id`), SKU (`sku`), or product search filter and returning up to 20 matching typed product stock records (`id`, `sku`, `name`, `description`, `stock`, `min_threshold`, `is_low_stock`), a `total_matched` count, and call status metadata from the existing TrackFlow Inventory Manager without mocked or hardcoded datasets.
- **FR-019**: All operational tools integrated into the support agent MUST be strictly read-only (query/read operations only) and MUST NOT expose or execute any capability to create, update, transition, or delete incident tickets, products, or orders.
- **FR-020**: Each operational tool MUST obey the single-responsibility principle: the Support Ticket Query Tool and the Inventory Stock Query Tool MUST be implemented as separate, distinct tools and graph nodes, never combined into a single multi-purpose tool.
- **FR-021**: If an underlying operational service requires authentication credentials (such as a bearer token or API key for HTTP calls), the tool adapter MUST load credentials exclusively from environment variables or application configuration, never hardcoding secrets in source code; when invoked in-process or against unauthenticated read endpoints, the authentication mode MUST be explicitly documented.
- **FR-022**: Every operational tool invocation MUST enforce an explicit, configurable numerical timeout (defaulting to a concrete value within 3.0 to 5.0 seconds, specifically `4.0` seconds) so that an unresponsive incident or inventory service never causes the workflow execution to hang.
- **FR-023**: The workflow MUST define an explicit fallback route triggered whenever an operational tool times out, encounters a service or transport error, or determines that the requested ticket or product record does not exist; on this route, the agent MUST respond honestly (e.g., `"I couldn't confirm the status of that ticket right now"` or `"I couldn't confirm the stock availability for that product right now"`) and MUST NEVER invent or guess statuses, dates, or stock quantities. In hybrid inquiries where an operational tool degrades or finds no record but static policy retrieval (`rag`) succeeds, the workflow MUST record the tool fallback, still execute `rag`, and return the verified policy answer alongside the honest inability-to-confirm message for the tool portion.
- **FR-024**: The agent MUST autonomously determine from the content of the user's natural-language question whether to route to static knowledge retrieval (RAG), the Support Ticket Query Tool, the Inventory Stock Query Tool, or a combination of static knowledge retrieval and operational tool(s), without requiring the user to explicitly specify which data source to use.
- **FR-025**: The execution trace of every run MUST explicitly record which data source(s) were consulted (RAG knowledge base, support ticket tool, inventory tool, or multiple sources) and the exact chronological order of node and tool execution; when multiple sources are selected for a hybrid inquiry, the workflow MUST execute them in the canonical sequence `ticket_tool` → `inventory_tool` → `rag`.
- **FR-026**: The automated evaluation suite MUST include at least two new routing evaluation tests verifying autonomous source selection:
  1. An operational question that MUST be resolved via a real-time operational tool (and NOT resolved via static RAG).
  2. A static policy/documentation question that MUST be resolved via RAG (and NOT resolved via an operational tool).
- **FR-027**: The automated evaluation suite MUST include an evaluation test verifying the fallback recovery behavior when an operational service is unavailable, times out, or a requested ticket record cannot be confirmed.

---

### Key Entities *(include if feature involves data)*

- **AgentState**: The minimal data contract transferred between workflow nodes, encapsulating the input question, sanitized topic, autonomous routing plan (selected sources), retrieved static context list with similarity scores, typed ticket tool output, typed inventory tool output, fallback/refusal status flags, generated response text, and execution metadata.
- **TicketToolInput**: Typed request contract for querying support incidents, supporting lookup by exact `ticket_id` or filtering by `status`, `category`, `origin`, and `branch`.
- **TicketToolOutput**: Typed response contract returned by the Support Ticket Query Tool, containing execution outcome status (`success`, `not_found`, `timeout`, `error`), up to 20 matching incident record(s) (`id`, `title`, `description`, `status`, `category`, `origin`, `branch`, `created_at`, `updated_at`), `total_matched` record count, latency in milliseconds, and sanitized error context if degraded.
- **InventoryToolInput**: Typed request contract for querying product inventory, supporting lookup by `product_id`, `sku`, or product search query.
- **InventoryToolOutput**: Typed response contract returned by the Inventory Stock Query Tool, containing execution outcome status (`success`, `not_found`, `timeout`, `error`), up to 20 matching product stock record(s) (`id`, `sku`, `name`, `description`, `stock`, `min_threshold`, `is_low_stock`), `total_matched` record count, latency in milliseconds, and sanitized error context if degraded.
- **AgentTrace**: A structured audit record representing a single workflow run, containing unique run ID, execution timestamp, ordered list of visited node names, explicit list of consulted data sources (`rag`, `ticket_tool`, `inventory_tool`) in execution order, step durations, fallback indicators, and step outcome summaries.
- **AgentCheckpoint**: A point-in-time snapshot of the state schema persisted at node boundaries, enabling inspection and potential resumption.
- **RetrievedContextChunk**: Representation of a policy chunk retrieved from vector storage, including source document name, section title, similarity score, and text content.
- **EvaluationTestCase**: An automated verification scenario consisting of a defined question input, expected routing and execution path criteria (nodes and data sources visited in order), and expected answer grounding or honest fallback criteria.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of agent execution runs generate a structured, queryable trace identifying the ordered sequence of visited nodes, the exact data source(s) used (static knowledge base, support ticket tool, inventory tool, or combination), and per-step latencies.
- **SC-002**: 100% of operational tool calls enforce an explicit numerical timeout of at most 5.0 seconds (default 4.0 seconds), guaranteeing that degraded or unresponsive incident/inventory services never stall an agent query beyond the timeout boundary.
- **SC-003**: 100% of failed, timed-out, or missing-record tool lookups traverse the explicit fallback route and produce an honest inability-to-confirm message with zero fabricated ticket statuses, categories, dates, or inventory stock numbers.
- **SC-004**: Across the automated routing evaluation suite, the agent achieves 100% accuracy in autonomously distinguishing questions requiring live operational tools from questions requiring static knowledge retrieval (RAG) without user-provided source hints.
- **SC-005**: 100% of integrated operational tools operate in strict read-only mode against the real TrackFlow incident and inventory data stores, with zero mutation capabilities (create, update, delete) and zero hardcoded/mocked production datasets.
- **SC-006**: Empty and out-of-scope inquiries are conditionally intercepted and routed to termination or refusal without invoking language model answer generation, eliminating 100% of ungrounded responses for unindexed topics.
- **SC-007**: The automated evaluation test suite in `tests/pipelines/` passes with a 100% success rate across all Part 1 grounding tests and Part 2 tool-routing and fallback tests in a single command invocation.
- **SC-008**: 100% of runtime exceptions occurring inside workflow nodes are intercepted by the endpoint layer, returning user-safe HTTP responses with zero raw stack traces or credentials leaked.

---

## Assumptions

- The TrackFlow Incident Manager and Inventory Manager both reside within the same monorepo backend (`services/api/`) and expose both HTTP endpoints (`GET /api/incidents`, `GET /api/incidents/{id}`, `GET /inventory/products/{id}`) and clean application service/repository ports (`IncidentService`, `InventoryService`). The tools may connect via either in-process service injection or HTTP transport (configurable), provided they read from the real persisted data stores (`db.json` via TinyDB and `inventory.db` via SQLite/SQLModel) and never from a parallel fake dataset.
- In the existing Incident Manager (`GET /api/incidents` and `GET /api/incidents/{id}`) and Inventory Manager (`GET /inventory/products/{id}`), read operations do not mandate user JWT authentication by default, though the HTTP client adapter supports optional environment-provided bearer token injection (`AGENT_INTERNAL_API_TOKEN` / `AGENT_API_BASE_URL`) for authenticated backend-to-backend deployments.
- Notice that `GET /inventory/products` in the HTTP router enqueues an asynchronous Celery aggregation task (HTTP 202), whereas `InventoryService` provides direct read-only synchronous access to real product stock records in `inventory.db`; therefore, using the in-process `InventoryService` (or querying product records directly via the service layer / HTTP product endpoint) provides immediate real-time stock data within the synchronous 4.0-second tool timeout window.
- A concrete numerical timeout of `4.0` seconds (configurable via environment settings within the 3–5 second guideline) is used as the default execution deadline for each operational tool call.
- A calibrated minimum similarity threshold of `0.62` remains the benchmark threshold for determining whether static retrieved context from Qdrant qualifies for policy answer generation.
