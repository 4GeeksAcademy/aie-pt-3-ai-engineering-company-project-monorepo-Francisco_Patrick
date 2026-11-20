# Quickstart Validation Guide: Support Agent with LangGraph

**Feature**: Support Agent with LangGraph  
**Branch**: `027-support-agent-langgraph`  
**Date**: 2026-11-17  
**Status**: Ready for Implementation  

This guide provides runnable scenarios to validate that the Support Agent with LangGraph operates according to its specification, correctly compiling the state graph, executing single-responsibility nodes, performing conditional routing, recording queryable traces, and serving HTTP requests with defensive error shielding.

---

## 1. Prerequisites & Environment Setup

Ensure your local environment has Python 3.14+ and dependencies synchronized:

```bash
# Verify active environment & dependencies
cd services/api
uv sync

# Ensure local test database / environment variables are configured
# Check .env or .env.example for QDRANT_HOST / QDRANT_PORT (default: in-memory or localhost:6333)
```

For contracts and data structure definitions, refer to:
- [data-model.md](./data-model.md)
- [contracts/agent-api.yaml](./contracts/agent-api.yaml)
- [contracts/agent-state.json](./contracts/agent-state.json)

---

## 2. Validation Scenario 1: Pipeline Evaluation Test Suite

Execute the automated evaluation suite verifying graph topology, node ordering, conditional routing, and factual policy grounding against company briefing documentation:

```bash
# Run the pipeline evaluation suite from the monorepo root
pytest tests/pipelines/test_support_agent_evaluation.py -v
```

### Expected Outcome:
- All evaluation test cases pass (100% success rate).
- `test_eval_standard_policy_reasoning_flow`: Verifies node sequence `["intake", "retrieval", "generation"]`, non-empty sources, and grounded return policy answer (30 days).
- `test_eval_conditional_refusal_for_unindexed_topic`: Verifies query about pharmaceutical refrigeration routes to `["intake", "retrieval", "refusal"]`, never executes `generation`, and emits `is_refusal=True`.
- `test_eval_empty_query_early_termination`: Verifies empty or whitespace query terminates at intake without executing retrieval or generation.
- `test_eval_storage_pricing_grounding`: Verifies answer accurately quotes Zaragoza (16 EUR) and Los Angeles (18 USD) storage rates.

---

## 3. Validation Scenario 2: Graph Build-Time Compilation Check

Validate that the LangGraph workflow compiles deterministically during service startup, failing immediately if nodes or edges are misconfigured:

```bash
# Execute unit tests for graph compilation and structural validation
pytest services/api/tests/unit/test_agent_workflow.py -v
```

### Expected Outcome:
- Test verifies `build_support_agent_graph()` produces a compiled `Pregel` / `CompiledStateGraph`.
- Test verifies an unconnected node or misconfigured conditional route raises a structural validation error at compile time prior to request execution.

---

## 4. Validation Scenario 3: End-to-End REST API Execution

Start the API service locally:

```bash
uv run --project services/api uvicorn main:app --host 127.0.0.1 --port 8000
```

### 4.1 Valid Policy Inquiry (Standard Path)
Submit a query regarding return policy:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is TrackFlow'\''s standard return window?"}'
```

**Expected Response (HTTP 200)**:
```json
{
  "query": "What is TrackFlow's standard return window?",
  "answer": "TrackFlow offers a 30-day return policy for standard inventory items...",
  "is_refusal": false,
  "sources": [
    {
      "source_document": "trackflow-returns-policy.en.md",
      "section": "Standard Return Policy",
      "similarity_score": 0.8842
    }
  ],
  "trace_id": "<uuid>",
  "node_sequence": ["intake", "retrieval", "generation"],
  "execution_time_ms": 115.4
}
```

### 4.2 Out-of-Scope Query (Honest Refusal Path)
Submit an inquiry absent from TrackFlow's knowledge base:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the temperature requirements for pharmaceutical refrigeration?"}'
```

**Expected Response (HTTP 200)**:
```json
{
  "query": "What are the temperature requirements for pharmaceutical refrigeration?",
  "answer": "TrackFlow internal documentation does not contain verified policy regarding pharmaceutical refrigeration...",
  "is_refusal": true,
  "sources": [],
  "trace_id": "<uuid>",
  "node_sequence": ["intake", "retrieval", "refusal"],
  "execution_time_ms": 42.1
}
```

### 4.3 Queryable Trace Inspection
Fetch the execution trace for the previous run:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/agent/trace/<trace_id>
```

**Expected Response (HTTP 200)**:
- Returns `AgentTraceResponseSchema` detailing per-node latencies and step execution timeline.

### 4.4 Defensive Error Shielding
Trigger a synthetic fault or malformed request to verify zero stack trace leakage:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": ""}'
```

**Expected Response**:
- Validation error (HTTP 422) or graceful refusal without exposing Python tracebacks or file paths.

---

## 5. Verification Gate Command

Run the complete regression suite to confirm zero side-effects across the monorepo:

```bash
# 1. Monorepo Pipeline Evaluation
pytest tests/pipelines/ -v

# 2. Knowledge Base & Agent Integration Tests
pytest services/api/tests/integration/test_knowledge_routes.py services/api/tests/unit/test_knowledge_service.py -v
```
