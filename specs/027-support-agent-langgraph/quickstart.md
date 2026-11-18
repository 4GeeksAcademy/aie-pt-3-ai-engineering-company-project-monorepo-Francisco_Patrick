# Quickstart Validation Guide: Support Agent with LangGraph — Explicit Reasoning & Operational Tools Outside the RAG

**Feature**: Support Agent with LangGraph — Explicit Reasoning & Operational Tools Outside the RAG  
**Branch**: `027-support-agent-langgraph`  
**Date**: 2026-11-18  
**Status**: Ready for Implementation  

This guide provides runnable scenarios to validate that the Support Agent with LangGraph operates according to its Part 1 (RAG inside compiled StateGraph) and Part 2 (Autonomous Real-Time Operational Tools outside the RAG) specification: compiling the 7-node state graph, autonomously routing between static knowledge retrieval (`rag`), the read-only Support Ticket Query Tool (`ticket_tool`), and the read-only Inventory Stock Query Tool (`inventory_tool`), enforcing the `4.0`s numerical timeout, traversing `tool_fallback` honestly on missing records or unavailable services, recording queryable multi-source traces, and serving HTTP requests with defensive error shielding.

---

## 1. Prerequisites & Environment Setup

Ensure your local environment has Python 3.14+ and dependencies synchronized:

```bash
# Verify active environment & dependencies
cd services/api
uv sync

# Optional environment configuration for operational tool timeouts and transport
# AGENT_TOOL_TIMEOUT_SECONDS=4.0 (default: 4.0, range: 3.0 - 5.0)
# AGENT_API_BASE_URL= (optional: defaults to in-process IncidentService & InventoryService)
# AGENT_INTERNAL_API_TOKEN= (optional: bearer token when using external HTTP transport)
```

For contracts and data structure definitions, refer to:
- [data-model.md](./data-model.md)
- [contracts/agent-api.yaml](./contracts/agent-api.yaml)
- [contracts/agent-state.json](./contracts/agent-state.json)
- [contracts/tools-schema.json](./contracts/tools-schema.json)

---

## 2. Validation Scenario 1: Pipeline Evaluation Test Suite (Part 1 + Part 2 Gates)

Execute the automated evaluation suite verifying graph topology, autonomous routing between operational tools and static RAG, canonical hybrid execution (`ticket_tool` → `inventory_tool` → `rag`), honest fallback recovery, and factual policy grounding:

```bash
# Run the pipeline evaluation suite from the monorepo root
uv run --project services/api pytest tests/pipelines/test_support_agent_evaluation.py -v
```

### Expected Outcome:
- All evaluation test cases pass (100% success rate):
  - **Part 1 RAG & Grounding Scenarios (`EVAL-001` – `EVAL-004`)**:
    - `test_eval_standard_policy_reasoning_flow`: Verifies node sequence `["intake", "retrieval", "generation"]`, `sources_consulted == ["rag"]`, non-empty sources, and grounded return policy answer (`30 days`).
    - `test_eval_conditional_refusal_for_unindexed_topic`: Verifies query about pharmaceutical refrigeration routes to `["intake", "retrieval", "refusal"]`, never executes `generation`, and emits `is_refusal=True`.
    - `test_eval_empty_query_early_termination`: Verifies empty or whitespace query terminates at `["intake", "refusal"]` without executing retrieval, tools, or generation.
    - `test_eval_storage_pricing_grounding`: Verifies answer accurately quotes Los Angeles (`18 USD`), Zaragoza (`16 EUR`), and `Miguel Torres` approval per company briefing.
  - **Part 2 Operational Tools & Autonomous Routing Scenarios (`EVAL-005` – `EVAL-009`)**:
    - `test_eval_autonomous_ticket_tool_routing`: Queries a live incident ticket (`INC-001`) without user source hints; verifies trace records `sources_consulted == ["ticket_tool"]`, `node_sequence == ["intake", "ticket_tool", "generation"]` (does NOT invoke `retrieval`), and returns live status, category, origin, and branch from the Incident Manager.
    - `test_eval_autonomous_rag_vs_tool_separation`: Confirms static policy inquiries resolve via `["rag"]` without invoking `ticket_tool` or `inventory_tool`.
    - `test_eval_autonomous_inventory_tool_routing`: Queries current warehouse stock for a live SKU (`TF-1001`); verifies trace records `sources_consulted == ["inventory_tool"]`, `node_sequence == ["intake", "inventory_tool", "generation"]`, and reports authentic stock quantity and threshold status from the Inventory Manager.
    - `test_eval_tool_fallback_on_missing_ticket_or_unavailable_service`: Verifies both missing ticket lookup (`INC-999999`) and simulated service timeout/unavailability traverse `"tool_fallback"`, complete within the timeout window, set `fallback_triggered=True`, and return an honest inability-to-confirm message without fabricated data.
    - `test_eval_hybrid_multi_source_canonical_order_and_partial_fallback`: Verifies hybrid questions execute in canonical sequence (`ticket_tool` → `retrieval` → `generation`, or `ticket_tool` → `retrieval` → `tool_fallback` → `generation` when the ticket is missing while RAG succeeds).

---

## 3. Validation Scenario 2: Unit Tests for 7-Node Graph & Operational Tool Contracts

Validate build-time graph compilation, single-responsibility operational tool adapters, 20-record cap with `total_matched`, read-only enforcement, and explicit `4.0`s timeout handling:

```bash
# Execute unit tests for workflow compilation, routing, and operational tools
uv run --project services/api pytest services/api/tests/unit/test_agent_workflow.py services/api/tests/unit/test_operational_tools.py -v
```

### Expected Outcome:
- Confirms `build_support_agent_graph()` registers all 7 required nodes (`intake`, `ticket_tool`, `inventory_tool`, `retrieval`, `tool_fallback`, `generation`, `refusal`) and fails at compile time if any node is missing or unreachable.
- Confirms `IncidentSupportTicketToolAdapter` and `InventoryStockQueryToolAdapter` enforce the 20-record cap, populate `total_matched`, abort calls exceeding the numerical timeout (`status="timeout"`), and expose zero mutation methods.

---

## 4. Validation Scenario 3: End-to-End REST API Execution

Start the API service locally:

```bash
uv run --project services/api uvicorn main:app --host 127.0.0.1 --port 8000
```

### 4.1 Live Support Ticket Query (Operational Tool Path)
Submit a natural-language question about a live support incident:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current status and category of ticket INC-001?"}'
```

**Expected Response (HTTP 200)**:
```json
{
  "query": "What is the current status and category of ticket INC-001?",
  "answer": "Support ticket INC-001 ...",
  "is_refusal": false,
  "fallback_triggered": false,
  "sources": [],
  "sources_consulted": ["ticket_tool"],
  "tool_calls": [
    {
      "tool_name": "ticket_tool",
      "status": "success",
      "total_matched": 1,
      "returned_count": 1,
      "latency_ms": 3.4,
      "error_message": null
    }
  ],
  "trace_id": "<uuid>",
  "node_sequence": ["intake", "ticket_tool", "generation"],
  "execution_time_ms": 14.2
}
```

### 4.2 Non-Existent Ticket Lookup (Honest Fallback Route)
Submit a query referencing a ticket ID that does not exist:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the status of ticket INC-999999?"}'
```

**Expected Response (HTTP 200)**:
```json
{
  "query": "What is the status of ticket INC-999999?",
  "answer": "I couldn't confirm the status of ticket 'INC-999999' right now because no matching incident record was found in the Incident Manager.",
  "is_refusal": false,
  "fallback_triggered": true,
  "sources": [],
  "sources_consulted": ["ticket_tool"],
  "tool_calls": [
    {
      "tool_name": "ticket_tool",
      "status": "not_found",
      "total_matched": 0,
      "returned_count": 0,
      "latency_ms": 2.1,
      "error_message": "No incident record matched ticket_id='INC-999999'."
    }
  ],
  "trace_id": "<uuid>",
  "node_sequence": ["intake", "ticket_tool", "tool_fallback"],
  "execution_time_ms": 9.8
}
```

### 4.3 Live Inventory Stock Query (Inventory Tool Path)
Submit a natural-language question about warehouse stock levels:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many units of SKU TF-1001 are currently in stock?"}'
```

**Expected Response (HTTP 200)**:
- Routes via `["intake", "inventory_tool", "generation"]` with `sources_consulted: ["inventory_tool"]` and reports live stock quantity and low-stock threshold status.

### 4.4 Queryable Trace Inspection
Fetch the structured execution trace for any run:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/agent/trace/<trace_id>
```

**Expected Response (HTTP 200)**:
- Returns `AgentTraceResponseSchema` detailing `node_sequence`, `sources_consulted`, `fallback_triggered`, `tool_calls`, `step_latencies`, and per-node `node_outputs`.

---

## 5. Verification Gate Command

Run the complete test suite to confirm zero regressions across the monorepo:

```bash
# 1. Monorepo Pipeline Evaluation Suite (Part 1 + Part 2)
uv run --project services/api pytest tests/pipelines/ -v

# 2. Agent Unit & Integration Test Suites
uv run --project services/api pytest services/api/tests/unit/test_agent_workflow.py services/api/tests/unit/test_operational_tools.py services/api/tests/integration/test_agent_routes.py -v
```
