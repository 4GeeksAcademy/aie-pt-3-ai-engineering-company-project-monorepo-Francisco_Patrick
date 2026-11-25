# Bug Fix: Resolve ChatSession `user_id` from domain customer context and separate operator ownership

- **Slug**: session-user-id-client-source
- **Fixed**: 2026-11-25
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

`ChatSession.user_id` (and the projected thread `user_id`) is now resolved server-side from the domain customer identity (`session_context.customer_id`) via a single domain/service resolver (`resolve_client_user_id`), falling back to `"unassigned"` when no customer context is bound yet and locking to the first `customer_id` seen (`merge_thread_session_context`). The caller-supplied `client_user_id` field and WebSocket query parameter were removed, and all per-operator authorization checks now compare `ChatThreadState.owner_user_id` (with read-time normalization of legacy persisted threads that stored the operator ID in `user_id`).

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/domain/agent/entities.py` | modified | Added `UNASSIGNED_CLIENT_USER_ID = "unassigned"`, `resolve_client_user_id`, and `merge_thread_session_context`; removed `client_user_id`; separated `owner_user_id` (operator) from `user_id` (client); normalized legacy persisted threads in `ChatThreadState.from_dict` |
| `services/api/domain/agent/ports.py` | modified | Added `session_context` parameter to `AgentChatThreadRepositoryPort.append_or_update_message` |
| `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py` | modified | Moved ownership validation and `list_threads_by_owner` filtering to `owner_user_id`; merged and locked `session_context` across `save_thread` and `append_or_update_message` |
| `services/api/application/services/support_agent_service.py` | modified | Added `SupportAgentService.resolve_client_user_id`; moved ownership checks in `get_or_create_thread_state`/`get_thread_history` to `owner_user_id`; dropped `client_user_id` parameter; propagated locked `session_context` through `stream_query` |
| `services/api/presentation/api/v1/agent.py` | modified | Dropped `client_user_id` WebSocket query param handling; updated REST history and WS fallback ownership checks to use `owner_user_id` and emit resolved client `user_id` (`"unassigned"` fallback) |
| `services/api/presentation/schemas/agent.py` | modified | Updated `ChatThreadHistoryResponseSchema.user_id` default and description to reflect chatting client `user_id` (`"unassigned"` fallback) |
| `packages/shared/types/knowledge.ts` | modified | Updated `user_id` JSDoc comments on `ChatThreadHistoryResponseDTO` and `ServerSessionSnapshotEventDTO` |
| `uis/backoffice/lib/supportAgentChatClient.ts` | modified | Stopped falling back to `owner_user_id` when parsing `session_snapshot.user_id`; defaults missing client `user_id` to `'unassigned'` |
| `services/api/tests/unit/agent/test_chat_session_briefing_contract.py` | modified | Updated contract tests to use `session_context.customer_id` and `"unassigned"` fallback; added legacy persistence and first-customer lock tests |
| `services/api/tests/test_websocket_streaming_chat.py` | modified | Updated unassigned thread snapshot expectations and added end-to-end WebSocket/REST test covering domain `customer_id`, streaming, interrupt, `?client_user_id=` spoofing rejection, and cross-operator `4003`/`403` isolation |
| `uis/backoffice/__tests__/supportAgentChatSessionContract.test.ts` | modified | Added test confirming `parseAgentChatStreamEvent` never leaks `owner_user_id` into `session.user_id` and defaults to `'unassigned'` |

## Diff Highlights (optional)

```python
def resolve_client_user_id(
    session_context: Optional["AuthenticatedSessionContext"] = None,
) -> str:
    """Resolve the chatting client `user_id` from domain `session_context.customer_id`."""
    if session_context is not None:
        customer_id = str(session_context.customer_id or "").strip()
        if customer_id:
            return customer_id
    return UNASSIGNED_CLIENT_USER_ID
```

## Tests Added or Updated

- `services/api/tests/unit/agent/test_chat_session_briefing_contract.py::test_session_user_id_is_chatting_client_not_operator` — verifies `ChatSession.user_id` is derived from `session_context.customer_id` while `owner_user_id` holds the operator.
- `services/api/tests/unit/agent/test_chat_session_briefing_contract.py::test_session_user_id_falls_back_to_unassigned_without_client_context` — verifies `"unassigned"` fallback when no customer context is bound.
- `services/api/tests/unit/agent/test_chat_session_briefing_contract.py::test_legacy_persisted_thread_with_operator_in_user_id_remains_owned_by_operator` — verifies legacy TinyDB documents with operator ID in `user_id` normalize to `owner_user_id` on read and enforce ownership.
- `services/api/tests/unit/agent/test_chat_session_briefing_contract.py::test_session_user_id_locks_to_first_customer_id_and_ignores_later_mismatch` — verifies `session_context.customer_id` locks on first bind and ignores conflicting subsequent customer IDs.
- `services/api/tests/test_websocket_streaming_chat.py::test_session_user_id_resolved_from_domain_customer_and_not_spoofable` — verifies REST history fallback (`"unassigned"`), WebSocket `?client_user_id=` query parameter ignore, binding `customer_id` from `session_context` across streaming and interruption, and cross-operator `4003`/`403` ownership rejection.
- `uis/backoffice/__tests__/supportAgentChatSessionContract.test.ts` — verifies `parseAgentChatStreamEvent` never falls back to `owner_user_id` and defaults missing client `user_id` to `'unassigned'`.

## Local Verification

- Commands run:
  - `services/api`: `.\.venv\Scripts\python.exe -m pytest tests/unit/agent/test_chat_session_briefing_contract.py tests/test_websocket_streaming_chat.py -q` → `27 passed, 2 warnings in 13.45s`
  - `uis/backoffice`: `npx.cmd jest supportAgentChat` → `2 passed, 16 tests passed`
  - `uis/backoffice`: `npx.cmd tsc --noEmit` → exit `0`
- Manual checks: Verified no remaining references to `client_user_id` exist in `services/api`, `uis/backoffice`, or `packages/shared`.

## Deviations from Assessment

- Clarifications (user-approved):
  - `ChatSession.user_id` is resolved from `AuthenticatedSessionContext.customer_id` (`session_context.customer_id`) attached to the thread on creation or first message with `session_context`.
  - When no customer context is known yet, `ChatSession.user_id` falls back to `"unassigned"`. Once a `customer_id` is bound on the thread, it locks to that first `customer_id` and ignores later mismatches.
  - `client_user_id` was dropped completely from `ChatThreadState`, service methods, and the WebSocket endpoint.

## Follow-ups

- When a ticket/customer picker is added to the back-office Support Agent chat view, include `session_context` (`customer_id`) on the initial `user_message` or thread initialization call so the session transitions from `"unassigned"` to the selected customer immediately.
