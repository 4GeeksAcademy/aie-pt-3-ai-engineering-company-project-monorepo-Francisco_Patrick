# Feature Specification: Support Agent with LangGraph

**Feature Branch**: `feature/langgraph-agent-base`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Feature: Support Agent with LangGraph. Overview: You already built the four functions of your RAG system (`setup`, `embed`, `retrieve`, `query`) and exposed them through a FastAPI endpoint. It works, but it's a black box: it takes in a question and returns an answer, without anyone — including you — being able to see what decisions it made along the way. Your tech lead opened a ticket with a clear requirement: before adding any new capability to the agent (Part 2 of this same project), the reasoning flow has to become explicit as a graph, with state, nodes, and transitions that can be traced and evaluated independently. Tech lead's note: 'I don't want you to rewrite the RAG logic from scratch — the retrieve and embed you already have work fine. What I want is that same behavior living inside a LangGraph graph, with single-responsibility nodes, and every run traced. If I can't see why the agent answered what it answered, I can't trust it in production.' Three things are implied in that ticket and are easy to miss: (1) the graph must be compiled before any execution, so structural errors are caught at build time rather than in production; (2) the state passed between nodes must be minimal and explicit, not the full conversation history; and (3) every run must produce a queryable trace, not just a final answer."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explicit, Traceable Reasoning Flow for Customer Inquiries (Priority: P1)

As a TrackFlow Support Coordinator or Commercial Operations Lead,
I want customer inquiries to be processed through an explicit state machine with distinct stages for input intake, context retrieval, and response synthesis,
So that every decision and data transformation is transparent, audit-ready, and independently verifiable rather than hidden in a black-box execution.

**Why this priority**:
Monolithic, black-box RAG pipelines obscure failure points, making it impossible to determine whether an erroneous answer resulted from malformed questions, missing retrieval context, or generation hallucinations. Making the flow explicit as a state graph is the prerequisite foundation for trusting automated agents in production.

**Independent Test**:
Can be fully verified by submitting a standard operational question (e.g., standard return policy or storage rates) and asserting that the system executes the single-responsibility intake node, followed by the retrieval node, followed by the answer generation node, producing an accurate grounded response with citations and recording each distinct stage.

**Acceptance Scenarios**:

1. **Given** an inquiry regarding TrackFlow's standard return policy ("What is TrackFlow's standard return window?"),
   **When** the agent workflow executes,
   **Then** the inquiry enters the question intake node, transitions to the retrieval node which fetches relevant policy chunks from verified company documentation, transitions to the generation node with the retrieved context, and returns a verified answer stating the 30-day return policy along with source citations.
2. **Given** an inquiry about warehouse storage rates in Zaragoza and Los Angeles,
   **When** the agent processes the request,
   **Then** retrieval produces matching storage pricing sections before generation is called, ensuring the generation stage does not re-invoke retrieval and remains strictly bounded by the retrieved context.

---

### User Story 2 - Conditional Branching and Honest Policy Refusal (Priority: P2)

As a Commercial Governance Lead,
I want the agent workflow to evaluate dynamic output conditions between steps and branch conditionally,
So that empty questions immediately halt without executing costly retrieval, and queries lacking verified documentation route to an honest refusal message instead of forcing generation on ungrounded context.

**Why this priority**:
Preventing hallucinations and wasted compute on unsupported topics is a core business requirement. Hardcoded linear sequences fail when prerequisites are unmet; explicit conditional branching guarantees that the agent never attempts to generate answers when no supporting context exists above the calibrated confidence threshold.

**Independent Test**:
Can be fully verified by submitting an empty/whitespace query and an out-of-scope query (e.g., pharmaceutical refrigeration policies), verifying that the workflow terminates early on empty input and conditionally routes to an honest refusal node when similarity thresholds are not met.

**Acceptance Scenarios**:

1. **Given** a blank or whitespace-only inquiry string,
   **When** the intake node evaluates the inquiry,
   **Then** the workflow immediately halts via a conditional edge without invoking vector retrieval or language models, returning a clear validation failure.
2. **Given** a query concerning policies absent from TrackFlow's knowledge base (e.g., temperature-controlled pharmaceutical storage),
   **When** the retrieval node executes and finds zero document chunks satisfying the calibrated similarity threshold,
   **Then** a conditional edge routes execution to a dedicated refusal node rather than the generation node, returning an honest standard refusal ("TrackFlow internal documentation does not contain verified policy regarding this inquiry...").

---

### User Story 3 - Queryable Execution Tracing and State Checkpointing (Priority: P3)

As a Tech Lead and AI Systems Engineer,
I want every execution run to record a structured, queryable trace of node visitations and persist state snapshots at meaningful transitions,
So that production runs can be audited post-hoc, execution anomalies can be debugged, and state can be inspected or resumed without parsing raw unstructured console logs.

**Why this priority**:
Production readiness requires observability. If an operator cannot query which nodes ran, in what exact order, what data each node received and emitted, and inspect intermediate checkpoints, the system cannot be safely maintained or scaled with multi-tool capabilities.

**Independent Test**:
Can be fully verified by executing inquiries through the agent, retrieving the resulting trace identifier or trace record, and asserting that the record exposes the exact ordered list of visited nodes, input/output state deltas, and timestamped checkpoints for every transition.

**Acceptance Scenarios**:

1. **Given** a completed agent inquiry execution,
   **When** an engineer or audit process queries the trace for that run,
   **Then** the trace details the sequence of executed nodes (e.g., intake -> retrieve -> generate -> end), the execution latency per node, and the state payload at each boundary.
2. **Given** a multi-step execution,
   **When** state transitions between nodes occur,
   **Then** a state checkpoint is verifiably persisted with a unique thread/run identifier, allowing point-in-time state inspection.

---

### User Story 4 - Automated Evaluation Suite and Knowledge Grounding Gates (Priority: P4)

As a Quality Assurance and Release Engineer,
I want an automated evaluation test suite runnable via a single command that validates trace topology, node sequence contracts, and knowledge grounding,
So that regressions in reasoning logic, routing conditions, or policy accuracy are caught automatically before deployment.

**Why this priority**:
Trace correctness alone is insufficient if answers become ungrounded from corporate facts. Automated evals validate both structural reasoning (did the right nodes run in the right order?) and factual adherence against the company's verified briefing documentation.

**Independent Test**:
Can be fully verified by executing the pipeline evaluation test suite in a single command (`pytest tests/pipelines/`), confirming that at least 3 distinct evaluation test cases pass, verifying trace node ordering and asserting answer grounding against TrackFlow policy documents.

**Acceptance Scenarios**:

1. **Given** an evaluation test asserting workflow sequencing,
   **When** the test runs against the trace of a standard inquiry,
   **Then** it verifiably confirms that the retrieval node executed prior to the generation node.
2. **Given** an evaluation test asserting factual policy grounding,
   **When** the test queries standard return policies from the TrackFlow briefing,
   **Then** the test asserts that the final answer contains the exact 30-day return window and correctly attributes return shipping responsibility as defined in `docs/rag/trackflow-BRIEFING.en`.
3. **Given** existing RAG unit and integration tests,
   **When** the full test suite runs,
   **Then** all pre-existing knowledge base tests continue to pass without regression.

---

### User Story 5 - Zero-Leakage API Integration Endpoint (Priority: P5)

As a Frontend or External Service Client,
I want to query the support agent through a standardized HTTP REST endpoint that invokes the compiled workflow and shields internal operational mechanics,
So that client applications receive clean structured responses and sanitized error messages even when internal nodes encounter faults.

**Why this priority**:
In accordance with the TrackFlow Constitution, public APIs must present strict Pydantic DTOs, execute asynchronously without blocking the event loop, and never leak raw stack traces or internal workflow graph primitives across HTTP boundaries.

**Independent Test**:
Can be fully verified by dispatching valid queries and intentionally simulated fault requests to the agent endpoint, confirming HTTP 200 with structured response bodies for successes and sanitized error payloads (zero stack traces) for failures.

**Acceptance Scenarios**:

1. **Given** a valid JSON request posted to the agent endpoint (`POST /agent/query` or equivalent),
   **When** the endpoint invokes the compiled graph,
   **Then** it returns HTTP 200 with the synthesized answer, source citations, and queryable trace identifier.
2. **Given** an unhandled internal exception or structural fault within an agent node,
   **When** the endpoint processes the failure,
   **Then** it returns an appropriate HTTP error status with a sanitized user-facing message, recording the full traceback in internal telemetry logs without exposing raw code lines or secrets in the HTTP response.

---

### Edge Cases

- **Empty or Whitespace Queries**: Inquiries containing only spaces, tabs, or newlines must not trigger vector search embeddings; they must conditionally terminate at intake with an informative refusal or validation status.
- **Out-of-Distribution / Zero-Hit Queries**: Queries with semantic similarity below the calibrated threshold (0.62) must not reach the language generation node with empty context; they must branch to a dedicated refusal node.
- **Oversized Queries or Prompt Injections**: Input text exceeding character boundaries or containing prompt manipulation markers must be sanitized at the intake node before reaching downstream retrieval or generation.
- **Vector Database Unavailability**: If the underlying vector store is temporarily unreachable or times out, the retrieval node must catch the error gracefully and route to an explicit degraded error state rather than crashing the graph runner.
- **Graph Structural Misconfiguration**: If a node lacks an outgoing edge or a required state field is omitted during development, compilation must fail at build/startup time before any requests are accepted.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define an explicit, minimal state schema containing only the user query, retrieved context chunks, synthesized answer, refusal indicator, and execution metadata, excluding full historical chat dialogs unless justified.
- **FR-002**: The system MUST implement single-responsibility workflow nodes: a question intake/validation node, a context retrieval node, an answer generation node, and an honest refusal node.
- **FR-003**: The context retrieval node MUST reuse existing retrieval and embedding logic from the codebase without duplicating vector search or embedding logic.
- **FR-004**: The answer generation node MUST accept only the pre-retrieved context chunks from the state and MUST NOT re-invoke retrieval or bundle retrieval and generation in a monolithic step.
- **FR-005**: The workflow MUST implement explicit conditional edges that evaluate state outputs (e.g., routing empty queries to termination, routing queries with zero qualifying context chunks to the refusal node, and routing qualified context to the generation node).
- **FR-006**: The workflow MUST be explicitly compiled prior to execution, raising deterministic compilation errors upon structural defects (unconnected nodes, invalid transition targets, or mismatched state schemas).
- **FR-007**: The workflow MUST incorporate state checkpointing at meaningful node transitions, persisting execution state linked to a verifiable thread or run identifier.
- **FR-008**: Every execution of the agent workflow MUST produce a queryable trace capturing node visitation sequence, execution timestamps/latencies, and input/output state payloads.
- **FR-009**: The system MUST provide an evaluation suite in the pipelines test suite (`tests/pipelines/`) runnable via a single test command.
- **FR-010**: The evaluation suite MUST include at least three verifiable test cases that inspect trace ordering, conditional branching, and output correctness.
- **FR-011**: At least one evaluation test case MUST assert that generated answers remain grounded in TrackFlow's verified briefing documentation (`docs/rag/trackflow-BRIEFING.en` or `docs/company-knowledge-base/`).
- **FR-012**: All pre-existing RAG and pipeline regression tests MUST continue to pass alongside the new agent evaluations.
- **FR-013**: The system MUST expose the compiled agent workflow via a dedicated HTTP REST endpoint (e.g., `POST /agent/query`) that delegates entirely to the workflow without embedding business logic in the route handler.
- **FR-014**: The API endpoint MUST handle runtime workflow failures defensively, returning sanitized error responses while strictly preventing raw stack traces or internal system paths from leaking to consumers.
- **FR-015**: The agent endpoint handler MUST execute asynchronously without blocking the server event loop, adhering to monorepo architectural standards.

---

### Key Entities *(include if feature involves data)*

- **AgentState**: The minimal data contract transferred between nodes, encapsulating the input question, sanitized topic, retrieved context list with similarity scores, generated response text, refusal boolean flag, and execution metadata.
- **AgentTrace**: A structured audit record representing a single workflow run, containing unique run ID, execution timestamp, ordered list of visited node names, step durations, and step outcome states.
- **AgentCheckpoint**: A point-in-time snapshot of the state schema persisted at node boundaries, enabling inspection and potential resumption.
- **RetrievedContextChunk**: Representation of a policy chunk retrieved from vector storage, including source document name, section title, similarity score, and text content.
- **EvaluationTestCase**: An automated verification scenario consisting of a defined question input, expected execution path criteria (e.g., nodes visited in order), and expected answer grounding criteria.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of agent execution runs generate a structured, queryable trace identifying the sequence of visited nodes and step latencies.
- **SC-002**: Empty and out-of-scope inquiries are conditionally intercepted and routed to termination or refusal without invoking language model answer generation, eliminating 100% of ungrounded responses for unindexed topics.
- **SC-003**: The automated evaluation test suite in `tests/pipelines/` passes with 100% success rate across at least 3 distinct trace and grounding scenarios in a single command invocation.
- **SC-004**: 100% of factual questions covering core TrackFlow policies (return windows, storage rates, carrier allocation) return answers accurately reflecting company documentation.
- **SC-005**: 100% of runtime exceptions occurring inside workflow nodes are intercepted by the endpoint layer, returning user-safe HTTP error representations with zero raw stack traces leaked.
- **SC-006**: Structural graph compilation validation catches 100% of misconfigured or disconnected nodes at application initialization prior to handling live traffic.

---

## Assumptions

- The existing vector store adapter (`QdrantVectorStoreAdapter`) and embedding adapter (`FastEmbedAdapter` / `EmbeddingServicePort`) provide reliable semantic search and will be consumed by the retrieval node without re-implementation.
- A calibrated minimum similarity threshold of 0.62 remains the benchmark threshold for determining whether retrieved context qualifies for answer generation.
- The workflow state is scoped to single inquiry-response runs; full multi-turn conversational history is intentionally omitted from the initial minimal state schema to preserve focus and token efficiency.
- Tracing will be implemented in a queryable structured storage or in-memory trace registry that can be accessed by tests and inspection tools without requiring external third-party SaaS subscriptions if offline.
- The Python environment managed by `uv` in `services/api` is the execution runtime for the agent service and pipeline tests.
