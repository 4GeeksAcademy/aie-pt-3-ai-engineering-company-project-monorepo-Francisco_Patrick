# Research: Support Agent with LangGraph

**Feature**: Support Agent with LangGraph  
**Branch**: `027-support-agent-langgraph`  
**Date**: 2026-11-17  
**Status**: Completed  

---

## 1. LangGraph StateGraph Architecture & Minimal State Schema

### Decision
Define an explicit, minimal Python `TypedDict` schema named `AgentState` containing only:
- `query`: `str` (sanitized input question)
- `top_k`: `int` (retrieval depth, defaults to 3)
- `min_score`: `float` (calibrated similarity threshold, defaults to 0.62)
- `contexts`: `List[RetrievedContext]` (retrieved context chunks satisfying threshold)
- `answer`: `str` (synthesized response or standardized refusal message)
- `is_refusal`: `bool` (flag indicating whether the inquiry was refused)
- `sources`: `List[SourceCitation]` (provenance metadata for verified documents)
- `trace_id`: `str` (unique execution run identifier)
- `node_history`: `List[str]` (ordered sequence of executed node identifiers)
- `error`: `Optional[str]` (sanitized error message if a step fails)

Multi-turn historical conversational message lists (`List[BaseMessage]`) are intentionally excluded from this initial minimal state schema.

### Rationale
- **Compliance with Tech Lead Ticket & FR-001**: The ticket specifies that state passed between nodes must be minimal and explicit, not the full conversation history. Passing minimal state minimizes token footprint, eliminates hidden state mutations across nodes, and simplifies state serialization and inspection.
- **LangGraph Best Practice**: In LangGraph 1.2+, `TypedDict` provides native support for state schema declaration, partial updates returned by nodes, and zero serialization friction with `StateGraph(AgentState)`.
- **Determinism**: Every field is strongly typed, deterministic, and maps directly to the domain entities defined in `domain.knowledge.entities`.

### Alternatives Considered
- *Full chat history (`messages: Annotated[list, add_messages]`)*: Standard LangChain chatbot approach. Rejected because this feature is a single-turn inquiry-response agent with explicit RAG verification. Preserving the full conversation history would violate the ticket requirement ("state passed between nodes must be minimal and explicit, not the full conversation history") and introduce unnecessary memory overhead.
- *Pydantic BaseModel as LangGraph State*: LangGraph supports Pydantic models for state, but partial updates and delta dictionaries are natively optimized for `TypedDict`, avoiding validation overhead on intermediate node transitions.

---

## 2. Single-Responsibility Nodes & Conditional Routing Protocol

### Decision
Decompose the support agent workflow into 4 single-responsibility nodes and 2 conditional routing edges:

#### Nodes:
1. `intake_node`: Validates input query, trims whitespace, normalizes shell escapes, checks minimum length (≥ 3 characters), and initializes `node_history` and `trace_id`.
2. `retrieval_node`: Generates query embeddings using `EmbeddingServicePort` and executes semantic similarity search against Qdrant via `VectorStorePort`. Filters results using `min_score` (0.62 threshold). Populates `contexts` in state.
3. `generation_node`: Ingests pre-retrieved `contexts`, calls `LLMGenerationPort` (or persona-aligned synthesis), runs `BusinessGuardrailValidator` to ensure corporate alignment, and extracts `sources` citations.
4. `refusal_node`: Generates a deterministic refusal message via `build_refusal_message(query)` when query is out-of-scope or retrieved similarity is below threshold. Sets `is_refusal = True` and empty sources.

#### Conditional Edges:
- `route_after_intake`:
  - If `query` is empty or invalid (< 3 chars): routes directly to `refusal_node` (or `END`).
  - Otherwise: routes to `retrieval_node`.
- `route_after_retrieval`:
  - If `len(contexts) == 0` (zero chunks above `min_score` threshold): routes to `refusal_node`.
  - If `len(contexts) > 0`: routes to `generation_node`.

Both `generation_node` and `refusal_node` transition directly to `END`.

### Rationale
- **Strict Decoupling (FR-002, FR-004)**: Ensures that retrieval is completely separated from generation. Generation never triggers retrieval, preventing duplicate vector lookups or recursive embedding loops.
- **Cost & Latency Optimization (FR-005, SC-002)**: Empty, malformed, or ungrounded queries are halted before reaching expensive language models, eliminating hallucinations for unindexed topics.
- **Testability**: Each node can be unit-tested in isolation by providing input state and verifying output state mutations.

### Alternatives Considered
- *Monolithic RAG Node*: Combining retrieval and generation inside one node. Rejected because the tech lead ticket explicitly demanded single-responsibility nodes whose decisions can be traced and evaluated independently.
- *Dynamic LLM-based Router Node*: Using an LLM call to decide whether to retrieve. Rejected because deterministic threshold gating on vector similarity (cosine score ≥ 0.62) is 100% reliable, zero-latency, and strictly obeys TrackFlow Constitution Principle VII.

---

## 3. Pre-Execution Graph Compilation & Build-Time Verification

### Decision
Implement an explicit compilation factory function `build_support_agent_graph(checkpointer=None) -> CompiledStateGraph` and compile the graph once during application startup or dependency injection (`get_support_agent_workflow()`).

Structural integrity is verified at build/compilation time:
- Validate that all nodes (`intake`, `retrieval`, `generation`, `refusal`) are registered.
- Validate that conditional routing functions cover all potential branch targets.
- Validate that all leaf paths terminate at `END`.
- Validate state schema compatibility.

### Rationale
- **Enforces Ticket Requirement (1)**: "The graph must be compiled before any execution, so structural errors are caught at build time rather than in production."
- **LangGraph Compilation Model**: `StateGraph.compile()` builds the underlying Pregel runner, verifies edge connectivity, and raises `ValueError` immediately if orphan nodes or unreachable targets exist.
- **Fail-Fast**: Any routing typo or missing node stops service initialization or test startup immediately, satisfying SC-006.

### Alternatives Considered
- *Runtime Dynamic Graph Construction*: Building the graph on every incoming HTTP request. Rejected because it incurs compilation overhead on every request and delays structural validation until user traffic arrives.

---

## 4. Queryable Execution Tracing & State Checkpointing

### Decision
Implement dual-layer observability:
1. **In-Workflow Execution Tracing (`AgentTrace` & `TraceRegistry`)**:
   - Each node appends its identifier to `node_history` and records timestamps/latencies.
   - A dedicated `AgentTrace` entity captures:
     - `trace_id`: UUID4 string
     - `query`: Original query
     - `node_sequence`: `["intake", "retrieval", "generation"]` or `["intake", "retrieval", "refusal"]`
     - `step_latencies`: Mapping of `node_name` -> duration in milliseconds
     - `total_duration_ms`: Total execution time
     - `is_refusal`: Boolean
     - `final_answer`: Resulting text
     - `source_count`: Number of cited documents
   - Persist completed traces to an in-memory/queryable thread-safe `TraceRegistry` accessible by test suites and diagnostic endpoints (`/agent/trace/{trace_id}`).
2. **LangGraph State Checkpointing**:
   - Compile the workflow with a LangGraph `checkpointer` (such as `MemorySaver` from `langgraph.checkpoint.memory`).
   - Every execution run passes a `thread_id` via `RunnableConfig` (`{"configurable": {"thread_id": trace_id}}`).
   - Enables point-in-time state inspection (`graph.get_state(config)`) at each node boundary.

### Rationale
- **Enforces Ticket Requirement (3) & FR-007, FR-008**: Every run must produce a queryable trace, not just a final answer.
- **Zero External SaaS Requirement**: Functions reliably in local development, CI/CD pipelines, and isolated production networks without requiring paid or network-dependent third-party tracing services (e.g. LangSmith or Langfuse), while maintaining full queryability.
- **Audit & Post-Hoc Debugging**: QA engineers and evaluation suites can query the exact sequence of nodes executed, latency per stage, and intermediate state deltas.

### Alternatives Considered
- *Logging only to stdout*: Printing messages via `logging.getLogger()`. Rejected because logs are unstructured, difficult to query programmatically in evaluation tests, and violate FR-008.
- *Mandatory Cloud Tracing (LangSmith)*: Excellent tool, but requires external API keys and internet access, violating monorepo offline test determinism.

---

## 5. Existing RAG Component Reuse

### Decision
Directly inject and reuse existing domain ports and adapters without duplicating code:
- `EmbeddingServicePort` (`FastEmbedAdapter`): generates 384-dimensional dense vectors using `BAAI/bge-small-en-v1.5`.
- `VectorStorePort` (`QdrantVectorStoreAdapter`): performs semantic search against the canonical `trackflow_knowledge` collection.
- `LLMGenerationPort` / Persona generation: synthesizes answers grounded in TrackFlow voice.
- `BusinessGuardrailValidator`: applies corporate compliance filters and enforces grounded facts.
- `build_refusal_message`: formats sanitized topic-aware refusal strings.

### Rationale
- **Fulfills Tech Lead Mandate**: "I don't want you to rewrite the RAG logic from scratch — the retrieve and embed you already have work fine. What I want is that same behavior living inside a LangGraph graph."
- **DRY & Hexagonal Consistency**: Existing adapters are already tested, tuned for the 0.62 similarity threshold, and compliant with Constitution Principle VII.

---

## 6. Pipeline Evaluation Suite & Grounding Verification

### Decision
Implement a specialized automated evaluation suite in `tests/pipelines/test_support_agent_evaluation.py`:
1. **Eval 1 (Standard Policy & Topology)**: Query standard return window ("What is TrackFlow's standard return window?"). Assert:
   - Node sequence: `["intake", "retrieval", "generation"]`
   - Retrieved chunks > 0 with similarity ≥ 0.62
   - `is_refusal == False`
   - Final answer cites `trackflow-returns-policy` or `trackflow-BRIEFING`
   - Factual grounding check: asserts answer contains "30" (days) and attributes return shipping fees correctly.
2. **Eval 2 (Conditional Branching & Honest Refusal)**: Query unindexed topic ("What is the temperature range for pharmaceutical refrigeration storage?"). Assert:
   - Node sequence: `["intake", "retrieval", "refusal"]`
   - `is_refusal == True`
   - `generation` node was NEVER executed
   - Refusal message contains standard honest refusal phrasing.
3. **Eval 3 (Input Validation & Early Termination)**: Query empty or whitespace-only string ("   "). Assert:
   - Node sequence: `["intake", "refusal"]` (or terminates at intake)
   - `retrieval` and `generation` nodes were NEVER executed
   - Latency < 50ms (zero vector compute).
4. **Eval 4 (Warehouse Storage Rates Grounding)**: Query storage pricing across locations ("What are the monthly storage rates for standard pallet in Zaragoza and Los Angeles?"). Assert:
   - Answer accurately reflects €18/pallet (Zaragoza) and $25/pallet (Los Angeles) per company briefing.

### Rationale
- **Fulfills FR-009, FR-010, FR-011, and SC-003**: Executable via `pytest tests/pipelines/` in a single command, verifying trace topology, conditional edges, and factual adherence against `docs/company-knowledge-base/` without regression.

---

## 7. Public API Endpoint Contract & Defensive Exception Shielding

### Decision
Expose the agent via FastAPI router `services/api/presentation/api/v1/agent.py`:
- `POST /api/v1/agent/query`:
  - Request: `AgentQueryRequestSchema` (`query: str`, `top_k: int = 3`, `min_score: Optional[float] = 0.62`, `thread_id: Optional[str] = None`)
  - Response: `AgentQueryResponseSchema` (`query: str`, `answer: str`, `is_refusal: bool`, `sources: List[KnowledgeSourceCitationSchema]`, `trace_id: str`, `node_sequence: List[str]`, `execution_time_ms: float`)
- `GET /api/v1/agent/trace/{trace_id}`:
  - Returns `AgentTraceResponseSchema` detailing step breakdown and timestamps.
- **Execution**: Handled asynchronously via `await run_in_threadpool(...)` to prevent blocking the main event loop.
- **Error Shielding**: Enclosed in defensive try/catch blocks that log tracebacks internally with structured logs and return user-safe HTTP 500 error messages with sanitized details, strictly preventing raw stack traces or internal paths from leaking (Constitution Principle IV).

### Rationale
- **Constitution Principles II & IV**: 100% explicit Pydantic response models, `Depends` dependency injection, non-blocking execution, and zero raw error leaks.
