# Quickstart & Validation Guide: Real-Time Bidirectional WebSocket Streaming Chat with True Generation Abort (Part 2)

**Feature Branch**: `035-websocket-streaming-chat`  
**Date**: 2026-11-24  
**Spec**: [spec.md](./spec.md) | **Contracts**: [websocket-chat-api.yaml](./contracts/websocket-chat-api.yaml) & [websocket-chat-events.schema.json](./contracts/websocket-chat-events.schema.json)

---

## 1. Prerequisites & Environment Setup

Verify the Python test environment and TypeScript workspace dependencies from the repository root:

```powershell
# 1. Verify Python test runner
pytest --version

# 2. Verify TypeScript static type checking across monorepo
npm run typecheck
```

> **Deterministic Synthesis Support**: Even without an external `LLM_API_KEY`, `GroundedGenerationAdapter` and `SupportAgentService` synthesize grounded policy and operational tool responses deterministically and stream them token-by-token over the WebSocket pub/sub bus, allowing 100% deterministic offline/CI testing of real-time streaming, mid-response interruption, redirection, and thread rehydration.

---

## 2. Running Automated Verification Suites

### 2.1 Backend WebSocket Streaming, True Generation Abort, Auth & Rehydration Tests (`pytest`)

Run the dedicated backend test suite verifying JWT handshake enforcement (`4001`), per-user thread ownership isolation (`4003`), pub/sub event decoupling (`token_chunk`, `generation_started`, `generation_interrupted`, `generation_completed`, `session_rehydrated`), true cooperative generation abort (`< 250ms`, zero trailing chunks), durable TinyDB thread history rehydration across restarts, and zero regression on existing agent guardrails/memory/tools:

```powershell
pytest services/api/tests/test_websocket_streaming_chat.py -v
```

**Expected Outcome**:
- 100% of test cases pass.
- Unauthenticated or invalid-JWT WebSocket connections are rejected with close code `4001` before any events are emitted (SC-002).
- Connecting as User B to a `thread_id` owned by User A is rejected with close code `4003` (FR-003).
- Multi-token assistant responses emit `generation_started` followed by multiple sequential `token_chunk` frames and a final `generation_completed` frame carrying `sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `guardrail_interventions`, and `trace_id` (SC-001).
- Sending `{"event": "interrupt"}` or a redirecting `{"event": "user_message", ...}` mid-stream cancels the active generation task within `< 250ms`, emits `generation_interrupted`, produces **0 subsequent `token_chunk` events** for the aborted turn, and persists the partial response with `status: "interrupted"` (SC-003, SC-004).
- Reconnecting with the same `thread_id` emits `session_rehydrated` (and matches `GET /api/v1/agent/threads/{thread_id}/history`) restoring all prior `user`, `completed`, and `interrupted` turns in order with zero duplicates (SC-005).

### 2.2 Existing Support Agent Regression Suite (`pytest`)

Verify zero regressions across the existing LangGraph Support Agent, operational tools, persistent memory, and guardrails test suites (SC-006):

```powershell
pytest services/api/tests/test_support_agent*.py services/api/tests/test_agent_*.py -v
```

### 2.3 Frontend WebSocket Chat Client, Live Rendering, Abort & Reconnection Tests (`jest` & `typecheck`)

Run the frontend unit/integration tests and workspace typecheck:

```powershell
npm --prefix uis/backoffice test -- supportAgentChat
npm run typecheck
```

**Expected Outcome**:
- Progressive `token_chunk` rendering updates the active assistant bubble in real time.
- Mid-response interruption preserves the partial message with an explicit `interrupted` status badge (never deleting or overwriting partial text) and immediately accepts replacement input.
- Unexpected WebSocket drops trigger progressive exponential backoff (`1s, 2s, 4s, 8s, 16s, 30s`), halting immediately on authentication rejection (`4001`), and deduplicating rehydrated turns by `turn_id`.

---

## 3. Manual End-to-End Validation Scenario

1. **Start the FastAPI Backend**:
   ```powershell
   cd services/api
   uvicorn main:app --reload --port 8000
   ```
2. **Start the Backoffice UI**:
   ```powershell
   npm --prefix uis/backoffice run dev
   ```
3. **Open the Support Agent Streaming Chat View**:
   - Log in to the backoffice UI (`http://localhost:3000/login`) and navigate to `/knowledge`.
   - Confirm the connection badge indicates **"WebSocket Conectado • Streaming en Tiempo Real"** and shows the bound `thread_id`.
4. **Verify Live Token Streaming**:
   - Submit: *"What is TrackFlow's standard return window and who covers return shipping costs?"*
   - Observe the assistant response stream progressively token-by-token into the chat bubble, followed by verified policy citations (`returns-policy`) and trace metadata upon `generation_completed`.
5. **Verify Mid-Response Interrupt, Preserve & Redirect**:
   - Submit a multi-part question: *"Compare storage rates in Los Angeles versus Zaragoza and explain the 180-day surcharge and discount approval rules."*
   - While tokens are streaming, click **"Interrupt / Stop"** (or immediately send a new question: *"Actually, which carrier is recommended for rural deliveries in Aragón?"*).
   - Confirm the first assistant turn stops immediately, preserves its partial text with an **"Interrupted"** badge, and the new assistant turn begins streaming right away.
6. **Verify Reconnect & Thread Rehydration**:
   - Reload the `/knowledge` page or toggle offline/online in browser DevTools.
   - Confirm the client reconnects automatically with the same `thread_id` and restores both the `interrupted` turn and all `completed` turns intact without duplicates.
