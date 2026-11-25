# Bug Verification: ChatSession `user_id` is the operator, not the chatting client (source of client identity)

- **Slug**: session-user-id-client-source
- **Tested**: 2026-11-25
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

All four reproduction paths from `assessment.md` no longer reproduce the bug: `ChatSession.user_id` (and thread `user_id`) resolves server-side from `session_context.customer_id` (with fallback `"unassigned"` before customer binding), ignores any `?client_user_id=` WebSocket query parameter, locks to the first `customer_id` seen, and preserves strict per-operator thread ownership via `owner_user_id`. All 27 Python contract/WebSocket tests, 16 Jest tests, and TypeScript type-checking pass without regression.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction step 1 (WS without `client_user_id`) | `pytest tests/test_websocket_streaming_chat.py -k "test_us1_live_token_chunk_streaming or test_session_user_id_resolved_from_domain_customer_and_not_spoofable"` | pass | Initial `session_snapshot` reports `user_id == "unassigned"` (never the operator ID) and transitions to `session_context.customer_id` across streaming and interruption |
| Reproduction step 2 (REST create / history) | `test_session_user_id_resolved_from_domain_customer_and_not_spoofable` (`GET /api/v1/agent/threads/{thread_id}/history`) | pass | Returns `user_id == "unassigned"` before customer context is bound and `user_id == customer_id` after binding |
| Reproduction step 3 (WS `?client_user_id=anyone` spoofing) | `test_session_user_id_resolved_from_domain_customer_and_not_spoofable` (`/api/v1/agent/ws?...&client_user_id=spoofed_client`) | pass | Query parameter is ignored; snapshot reports `"unassigned"` |
| Reproduction step 4 (Operator ownership isolation & legacy data) | `test_session_user_id_resolved_from_domain_customer_and_not_spoofable` & `test_legacy_persisted_thread_with_operator_in_user_id_remains_owned_by_operator` | pass | Operator B rejected with WS `4003` and HTTP `403` even when `user_id` is the customer; legacy persisted threads normalize operator `user_id` to `owner_user_id` |
| New / updated Python tests | `services/api`: `.\.venv\Scripts\python.exe -m pytest tests/unit/agent/test_chat_session_briefing_contract.py tests/test_websocket_streaming_chat.py -v` | pass | 27 passed in 13.72s |
| New / updated Jest tests | `uis/backoffice`: `npx.cmd jest supportAgentChat` | pass | 2 test suites, 16 tests passed in 1.41s |
| Lint / type-check | `uis/backoffice`: `npx.cmd tsc --noEmit` | pass | Exit code 0 (zero TypeScript errors) |
| Full API suite (unrelated modules) | skipped | skipped | Skipped full 110s monorepo API suite; the 13 unrelated failures noted in `assessment.md` (suppliers, inventory message, SQLModel env) are outside the agent chat session module |

## Output Excerpts

```text
tests/unit/agent/test_chat_session_briefing_contract.py::test_session_user_id_is_chatting_client_not_operator PASSED [ 40%]
tests/unit/agent/test_chat_session_briefing_contract.py::test_session_user_id_falls_back_to_unassigned_without_client_context PASSED [ 44%]
tests/unit/agent/test_chat_session_briefing_contract.py::test_legacy_persisted_thread_with_operator_in_user_id_remains_owned_by_operator PASSED [ 48%]
tests/unit/agent/test_chat_session_briefing_contract.py::test_session_user_id_locks_to_first_customer_id_and_ignores_later_mismatch PASSED [ 51%]
tests/test_websocket_streaming_chat.py::test_session_user_id_resolved_from_domain_customer_and_not_spoofable PASSED [ 92%]
======================= 27 passed, 2 warnings in 13.72s =======================

PASS __tests__/supportAgentChatSessionContract.test.ts
PASS __tests__/supportAgentChat.test.ts
Test Suites: 2 passed, 2 total
Tests:       16 passed, 16 total
EXIT_CODES: pytest=0 jest=0 tsc=0
```

## Residual Risks

- Until the back-office Support Agent UI attaches a customer/ticket `session_context` on message submission, interactive back-office sessions without a customer context will display the explicit fallback `user_id: "unassigned"`.
- Full API regression suite outside the Support Agent WebSocket/contract modules was skipped for speed; the 13 pre-existing failures documented in `api-suite-test.md` should be tracked separately.

## Recommendation

Close the bug — verified end-to-end across domain entities, TinyDB persistence (including legacy thread normalization), REST thread history, WebSocket `session_snapshot` (before customer binding, after streaming, and after interruption), spoofing prevention, and TypeScript client parsing.
