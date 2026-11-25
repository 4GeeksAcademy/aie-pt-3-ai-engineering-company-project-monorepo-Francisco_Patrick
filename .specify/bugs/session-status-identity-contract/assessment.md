# Bug Assessment: Session status enum and identity fields deviate from briefing

- **Slug**: session-status-identity-contract
- **Created**: 2026-11-25
- **Source**: pasted text (follow-up to `simulated-streaming-session-contract`)
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim)

> You're emitting `streaming`/`disconnected` states outside of `active|interrupted|closed`. Correct these values/entities and add a test against the briefing. `session_snapshot` and `interrupt_requested` are already correct. If you want to align the session with the briefing, you're using `agent_id='trackflow-support-agent'` and `user_id` of the back-office operator, but the briefing requires `agent_id='first_line_cx'` and `user_id` of the chatting client.

## Symptom

`ChatSession.status` can take `streaming` and `disconnected`, which are outside the briefing enum `active | interrupted | closed`. Sessions are also created with `agent_id="trackflow-support-agent"` and `user_id` = back-office operator, whereas the briefing requires `agent_id="first_line_cx"` and `user_id` = the chatting client.

## Reproduction

1. Build a `ChatThreadState` whose last message is an assistant turn with `status="streaming"`; `.session.status` returns `"streaming"` (`entities.py:956-957`).
2. `ChatSession.from_dict({...})` without `agent_id` yields `trackflow-support-agent` (`entities.py:915`); `status="disconnected"` is accepted (`entities.py:909`).
3. `SupportAgentService` persists `session_status="streaming"` (`support_agent_service.py:836, 871`).
4. The TS client parser falls back to `'trackflow-support-agent'` and accepts `streaming`/`disconnected` (`supportAgentChatClient.ts:37-44, 434`).

[NEEDS CLARIFICATION: the briefing's `ChatSession` contract text was not found in the repo (`docs/**/*BRIEFING*` and `memory-bank` have no `first_line_cx`/`ChatSession` match). Values are taken from the report only.]

## Suspected Code Paths

- `services/api/domain/agent/entities.py:53-59` — `ChatSessionStatus` includes `streaming`, `disconnected`.
- `services/api/domain/agent/entities.py:870-921` — `ChatSession` defaults `agent_id`; `from_dict` allows the 5-value set.
- `services/api/domain/agent/entities.py:924-969` — `ChatThreadState` defaults; `session` property derives `"streaming"`.
- `services/api/application/services/support_agent_service.py:326-411, 836, 871, 975, 1322` — creates threads with `user_id=cleaned_owner` (operator) and sets `session_status`.
- `services/api/presentation/api/v1/agent.py:614-622` — WebSocket/REST thread creation with the authenticated operator's `user_id`.
- `services/api/domain/agent/ports.py:450`, `infrastructure/adapters/tinydb_chat_thread_repository.py:162-242` — status/user propagation and persistence.
- `packages/shared/types/knowledge.ts:77-99, 311-353` — `ChatSessionStatus`, doc comments naming the old agent.
- `uis/backoffice/lib/supportAgentChatClient.ts:37-44, 429-451` — `VALID_SESSION_STATUSES`, fallback agent id.
- `uis/backoffice/hooks/useSupportAgentChat.ts:227, 358` and `SupportAgentChatPanel.tsx:89` — `'disconnected'` here is the client *connection* status, not session status; leave as is.
- `services/api/tests/test_websocket_streaming_chat.py:112, 776, 842+` — existing session assertions to update/extend.

## Root Cause Hypothesis

The previous fix introduced `ChatSession` with a superset enum that mixes turn state (`streaming`) and transport state (`disconnected`) into session state, and defaulted identity to the back-office operator and the product-specific agent name. Confidence: high for status/agent_id; medium for the `user_id` source.

## Proposed Remediation

**Preferred**:
- Restrict `ChatSessionStatus` to `"active" | "interrupted" | "closed"` in Python and TS; update `from_dict` and `VALID_SESSION_STATUSES`.
- Remove the `streaming` derivation in `ChatThreadState.session`; an in-flight turn keeps the session `active` (turn-level `streaming` stays in `ChatTurnStatus`). Replace `session_status="streaming"` calls with `"active"`. Normalize legacy persisted values on read (`streaming`→`active`, `disconnected`→`interrupted`).
- Default/fallback `agent_id` to `first_line_cx` (Python, TS, doc comments); accept the old value only on read of legacy data.
- Bind `ChatSession.user_id` to the chatting client's id; keep operator identity in a separate field (`owner_email` / `session_context`) so ownership/authorization checks still work. Leave `client_id`, `session_snapshot`, `interrupt_requested` unchanged.

**Alternatives**:
- Keep the wide enum internally and coerce only at serialization: less churn, but non-compliant values stay reachable.

**Files likely to change**:
- `services/api/domain/agent/entities.py`, `ports.py`, `infrastructure/adapters/tinydb_chat_thread_repository.py`
- `services/api/application/services/support_agent_service.py`, `services/api/presentation/api/v1/agent.py`
- `packages/shared/types/knowledge.ts`
- `uis/backoffice/lib/supportAgentChatClient.ts`, `uis/backoffice/hooks/useSupportAgentChat.ts`
- `services/api/tests/test_websocket_streaming_chat.py`

**Tests to add or update**:
- Python contract test (e.g. `services/api/tests/unit/agent/test_chat_session_briefing_contract.py`): session status is always in `{active, interrupted, closed}` for streaming/interrupted/error threads and legacy `from_dict` input; default `agent_id == "first_line_cx"`; `user_id` is the chatting client, not the operator.
- WebSocket test: `session_snapshot` carries compliant `status`, `agent_id`, `user_id` during and after streaming and interrupt.
- Vitest for `parseServerEvent` normalizing `streaming`/`disconnected` and defaulting to `first_line_cx`.

## Risks & Considerations

- Persisted TinyDB threads with legacy values need read-time normalization.
- Ownership checks currently rely on `user_id == operator`; switching to the client id needs a separate operator-ownership field.
- UI that uses session `streaming` for the Stop button must use turn status instead.
- Strict TS rules apply (no `any`, `import type`, explicit return types, JSDoc).

## Open Questions

- [NEEDS CLARIFICATION: where is the briefing's `ChatSession` section (path/wording)?]
- [NEEDS CLARIFICATION: legacy `disconnected` → `interrupted` or `closed`?]
- [NEEDS CLARIFICATION: where does the chatting client's `user_id` come from when an operator drives the back-office chat UI?]
