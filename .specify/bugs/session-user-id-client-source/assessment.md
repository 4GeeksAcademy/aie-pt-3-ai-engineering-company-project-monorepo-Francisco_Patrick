# Bug Assessment: ChatSession `user_id` is the operator, not the chatting client (source of client identity)

- **Slug**: session-user-id-client-source
- **Created**: 2026-11-25
- **Source**: pasted text (follow-up to `session-status-identity-contract`, see its `test.md` Recommendation and `api-suite-test.md`)
- **Verdict**: valid
- **Severity**: medium

## Report (summarized)

Briefing: `ChatSession.user_id` must be the chatting client. The previous fix left it as the back-office operator unless the caller passes a `client_user_id`. `test.md` asks to wire `client_user_id` through the UI and the REST create endpoint. The user's decision: the client `user_id` must come from the domain (the thread/ticket the operator is answering), not from the UI. The notes only specify `user_id`; `client_user_id` is a name introduced by the previous fix.

## Symptom

`session_snapshot` and thread creation report `user_id` = operator in every path except the WebSocket when the browser sends `?client_user_id=`. Expected: `user_id` = the client of the thread, resolved server-side and not spoofable.

## Reproduction

1. Open the WebSocket without `client_user_id`: snapshot `user_id` is the operator id (`agent.py:887`, `agent.py:896`: `client_user_id or user_id`).
2. Create a thread via REST: `user_id=str(current_user.id)` (`agent.py:600-623`); there is no client field at all.
3. Open the WebSocket with `?client_user_id=anyone`: the value is accepted verbatim (`agent.py:852-854`), so any authenticated operator can set an arbitrary client identity.
4. Ownership checks compare `existing.user_id != user_id` (`agent.py:611`, `agent.py:879`, `support_agent_service.py:308, 361`) against the operator id, so `user_id` currently doubles as the owner.

[NEEDS CLARIFICATION: not reproduced by running the app; steps are derived from reading the code.]

## Suspected Code Paths

- `services/api/presentation/api/v1/agent.py:852-854, 887, 896` — client id read from the query string and echoed as `user_id`.
- `services/api/presentation/api/v1/agent.py:600-623` — REST create uses the operator as `user_id` and has no client source.
- `services/api/presentation/api/v1/agent.py:611, 879` and `support_agent_service.py:304-311, 358-364` — ownership uses `user_id`; it must move to an owner field before `user_id` can become the client.
- `services/api/application/services/support_agent_service.py:299, 335, 413, 438, 449` — `client_user_id` plumbing (the added field).
- `services/api/domain/agent/entities.py`, `ports.py`, `infrastructure/adapters/tinydb_chat_thread_repository.py:139, 223` — `client_user_id` persisted on the thread.
- `services/api/presentation/api/v1/agent.py:114-121, 996-1007` and `presentation/schemas/agent.py:19` — `session_context.customer_id` ("Authenticated customer or brand account ID") is the only domain-level customer identifier found. It arrives per user message, not at thread creation; `support_agent_service.py:338` creates threads with `session_context=None`.
- `services/api/tests/unit/agent/test_chat_session_briefing_contract.py:69` — test builds `client_user_id="client_9"`; it will need to follow the new design.
- `uis/backoffice/lib/supportAgentChatClient.ts` — client side of the contract (UI should not send an identity).

[NEEDS CLARIFICATION: no thread-to-ticket/customer link was found in the thread entity or the create path. Whether a ticket id or customer is attached to a thread at creation was not verified.]

## Root Cause Hypothesis

`user_id` was kept as the authenticated operator because it is the only identity known when a thread is created, and it also serves as the owner for authorization. The previous fix added an optional client-supplied `client_user_id` to get around this instead of deriving the client from domain data. The client identity is therefore both optional and untrusted. Confidence: high for the mechanism; medium for the best domain source, because `customer_id` arrives late (per message) and may not be a per-thread attribute.

## Proposed Remediation

**Preferred**:
- Resolve the client identity on the server from domain data: the customer/ticket attached to the thread (`session_context.customer_id`, or a ticket-to-customer lookup if the thread links to a ticket). One service method, used by both REST create and WebSocket, sets `ChatSession.user_id`.
- Stop accepting `client_user_id` from the query string and the UI; remove it from the public API. Keep it only if needed internally, otherwise drop the field.
- Move ownership checks to a dedicated owner field (`owner_user_id` / `owner_email`, which already exist) so `user_id` can be the client without breaking authorization.
- Explicit fallback when no client is known (e.g. `unassigned`), never the operator id. Legacy threads that hold the operator in `user_id` are read as owner.
- Because the customer may only be known on the first user message, update `user_id` when `session_context.customer_id` first arrives, and keep it stable afterwards (decide whether a later mismatch is rejected).

**Alternatives**:
- Keep a validated optional `client_user_id` in the REST create body: less domain work, but the identity is still caller-supplied unless the server verifies it against the ticket.
- Let the UI send a ticket/customer reference and resolve it server-side: reliable if the UI already knows the ticket, but still a request parameter to validate.

**Files likely to change**:
- `services/api/presentation/api/v1/agent.py`, `presentation/schemas/agent.py`
- `services/api/application/services/support_agent_service.py`
- `services/api/domain/agent/entities.py`, `ports.py`
- `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py`
- `packages/shared/types/knowledge.ts`, `uis/backoffice/lib/supportAgentChatClient.ts`

**Tests to add or update**:
- WebSocket `session_snapshot` test: a thread with a customer yields `user_id == customer_id` and not the operator; same after streaming and interrupt.
- REST create test: `user_id` is the resolved client; no client gives the explicit fallback.
- Ownership test: operator B cannot open operator A's thread even though `user_id` is now the client.
- Security test: a `client_user_id` query param is ignored.
- Legacy-data test: a persisted thread with the operator in `user_id` is still owned by that operator.
- Update `test_chat_session_briefing_contract.py:69`.

## Risks & Considerations

- Authorization regression if ownership checks keep comparing `user_id` after it changes meaning.
- Persisted TinyDB threads need read-time normalization.
- Removing `client_user_id` is a contract change for anything already sending it; check the UI and the fix's tests.
- `customer_id` is per message and may be absent; the fallback will be common until a per-thread customer link exists.
- The 13 failures in `api-suite-test.md` (suppliers 400 vs 422, `Supplier.status`, inventory message, SQLModel env, agent refusal and memory proposal) do not touch this code, but were not compared against the commit before the fix.
- Strict TS rules apply (no `any`, `import type`, explicit return types, JSDoc).

## Open Questions

- [NEEDS CLARIFICATION: is a thread linked to a ticket or customer at creation, and where is that stored?]
- [NEEDS CLARIFICATION: is `session_context.customer_id` the same identity as the briefing's chatting-client `user_id`?]
- [NEEDS CLARIFICATION: fallback value and behaviour when no client is known (and when `customer_id` changes mid-thread)?]
- [NEEDS CLARIFICATION: are the 13 API suite failures pre-existing?]
