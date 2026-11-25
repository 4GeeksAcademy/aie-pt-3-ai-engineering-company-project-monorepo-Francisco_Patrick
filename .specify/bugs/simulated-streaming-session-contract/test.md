# Bug Verification: Simulated Token Streaming, Unaborted LLM Generation & ChatSession / Event Naming Mismatch

- **Slug**: simulated-streaming-session-contract
- **Tested**: 2026-11-25
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: `SupportAgentService.stream_query` now decouples pre-generation state preparation (`_prepare_pre_generation_state`) from incremental token generation (`_iter_generation_deltas` / `stream_grounded_answer` with `stream=True` HTTP SSE streaming), aborts in-flight generation immediately when `abort_event` is triggered via `interrupt_requested`, and exposes the `ChatSession` contract (`agent_id`, `client_id`, `user_id`, `status`) alongside `user_id`, `session_snapshot`, and `interrupt_requested` across backend and frontend layers. No regressions were found in the WebSocket streaming chat, frontend unit test, or strict TypeScript type-check suites.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests/test_websocket_streaming_chat.py -v` | pass | Verified `_prepare_pre_generation_state` no longer invokes blocking `generate_grounded_answer`, `GroundedGenerationAdapter.stream_grounded_answer` sends `stream=True` and closes the HTTP SSE stream mid-flight on `abort_event`, and `ChatSession`, `user_id`, `session_snapshot`, and `interrupt_requested` match the specification. |
| New / updated tests | `.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests/test_websocket_streaming_chat.py -v` & `npm.cmd test --prefix uis/backoffice -- __tests__/supportAgentChat.test.ts` | pass | 12/12 backend WebSocket & streaming tests passed; 7/7 frontend unit tests in `supportAgentChat.test.ts` passed. |
| Regression suite | `.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests/test_websocket_streaming_chat.py -v` | pass | All US1–US5 WebSocket streaming, mid-stream interruption/redirection, auth handshake, session rehydration (`session_snapshot`), and broker pub/sub isolation tests passed. |
| Lint / type-check | `npx.cmd tsc --noEmit --project uis/backoffice/tsconfig.json` | pass | Exited with code 0 (zero TypeScript compiler or strict typing errors). |

## Output Excerpts

```text
services\api\tests\test_websocket_streaming_chat.py::test_us1_live_token_chunk_streaming_and_generation_completed_metadata PASSED [  8%]
services\api\tests\test_websocket_streaming_chat.py::test_us1_legacy_agent_ws_route_and_guardrail_refusal_streaming PASSED [ 16%]
services\api\tests\test_websocket_streaming_chat.py::test_us2_true_generation_abort_on_interrupt_and_partial_preservation PASSED [ 25%]
services\api\tests\test_websocket_streaming_chat.py::test_us2_mid_stream_redirection_aborts_first_turn_and_streams_second_turn PASSED [ 33%]
services\api\tests\test_websocket_streaming_chat.py::test_us2_websocket_idle_interrupt_is_safe_noop PASSED [ 41%]
services\api\tests\test_websocket_streaming_chat.py::test_us2_high_latency_abort_fallback_finalizer_prevents_race_and_duplicate_events PASSED [ 50%]
services\api\tests\test_websocket_streaming_chat.py::test_us3_unauthenticated_and_invalid_jwt_websocket_connections_rejected_with_4001 PASSED [ 58%]
services\api\tests\test_websocket_streaming_chat.py::test_us3_first_frame_authenticate_and_cross_operator_thread_ownership_isolation PASSED [ 66%]
services\api\tests\test_websocket_streaming_chat.py::test_us3_handshake_thread_and_session_id_validation_and_token_log_redaction PASSED [ 75%]
services\api\tests\test_websocket_streaming_chat.py::test_us4_reconnect_and_server_restart_rehydrate_completed_and_interrupted_turns PASSED [ 83%]
services\api\tests\test_websocket_streaming_chat.py::test_us5_event_broker_pubsub_isolation_fanout_and_strict_domain_alignment PASSED [ 91%]
services\api\tests\test_websocket_streaming_chat.py::test_true_llm_streaming_and_mid_generation_abort_stops_model_stream PASSED [100%]
======================= 12 passed, 2 warnings in 11.95s =======================
```

```text
PASS __tests__/supportAgentChat.test.ts
  Support Agent Bidirectional WebSocket Streaming Chat (US1 - US5)
    US1: token_chunk frame parsing, progressive token accumulation, and completion metadata
      √ progressively accumulates token_chunk deltas into the active streaming assistant bubble and transitions to completed (5 ms)
    US2: mid-response interrupt button, partial text preservation, and redirection
      √ preserves partial assistant content with status="interrupted" and ignores any late trailing token chunks (6 ms)
      √ renders Interrupt / Stop button during streaming, triggers onInterrupt, and displays Interrupted badge on preserved turn (36 ms)
    US3: WebSocket JWT URL binding and permanent halt on 4001/4003 close codes
      √ attaches thread_id, session_id, and JWT token to the WebSocket URL and identifies 4001/4003 as permanent auth close codes (17 ms)
    US4: Progressive exponential backoff (1s..30s) and turn deduplication on session_rehydrated
      √ calculates progressive exponential backoff delays of 1s, 2s, 4s, 8s, 16s capped at 30s (1 ms)
      √ deduplicates rehydrated turns by turn_id while preserving both completed and interrupted turns in order (1 ms)
    US5: Strict Support Agent domain field alignment and rejection of RFP SSE schemas
      √ rejects any frame containing Part 1 RFP SSE fields (rfp_ticket_created, rfp_id, services_requested) (2 ms)

Test Suites: 1 passed, 1 total
Tests:       7 passed, 7 total
```

## Residual Risks

- Running `test_true_llm_streaming_and_mid_generation_abort_stops_model_stream` in standalone isolation (`-k`) without the fixture initialization performed by the WebSocket endpoint tests requires passing an explicit `KnowledgeRuntimeConfig` to `get_support_agent_service(config=KnowledgeRuntimeConfig())` because `get_support_agent_service`'s default parameter is a FastAPI `Depends(...)` sentinel when called outside FastAPI's dependency injector.
- Live external LLM provider SSE streaming (OpenAI `/v1/chat/completions` and Gemini `:streamGenerateContent?alt=sse`) is validated via a mock HTTP streaming client in CI/local tests rather than live external network calls.

## Recommendation

Close the bug — verified end-to-end across backend streaming generation, mid-flight cancellation, domain/presentation schema contracts, and frontend TypeScript client integration.
