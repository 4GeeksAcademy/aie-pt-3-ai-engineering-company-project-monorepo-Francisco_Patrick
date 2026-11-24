# Bug Assessment: Minor Risks and Review Observations in Real-Time SSE RFP Notifications

- **Slug**: sse-rfp-notifications-risks
- **Created**: 2026-11-24T15:58:00+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

```text
# Observaciones y Riesgos Menores

1. Deduplicación en servidor acotada a maxlen=256: En RFPNotificationBroadcaster.publish_ticket_created, _published_ticket_ids es una deque(maxlen=max_history). Si se superan 256 tickets y se reintenta un ticket_id antiguo expulsado de la cola, podría volver a emitirse; el cliente sigue deduplicando por ticket_id en UI.
2. Reconciliación REST en useRFPNotifications.ts: reconcileMissedTickets solicita ?limit=50. Si durante una desconexión prolongada se registran más de 50 tickets, los anteriores al corte quedarán fuera de esa ventana inicial hasta paginar o refrescar.
3. Verificación de UI en entorno de test: El diff añade pruebas unitarias/de integración en rfpNotifications.test.ts (parsing, auth, backoff, replay y deduplicación), pero no incluye pruebas renderizando RFPIntakePage / RFPRealtimeNotificationBanner con React Testing Library.
4. Higiene del diff: .specify/feature.json cambia feature_directory de specs/033-rfp-approval-completion a specs/034-sse-rfp-notifications, y se incluyen artefactos de especificación en specs/034-sse-rfp-notifications/ junto a docs/real-time-notification/. Verifica que el estado de specs/034-sse-rfp-notifications/spec.md (Draft) y los comandos de verificación hayan sido ejecutados en tu entorno antes del merge a main.
```

## Symptom

During post-implementation code review of Feature 034 (`034-sse-rfp-notifications`), four minor architectural limits, verification gaps, and hygiene items were flagged:
1. Server deduplication memory is capped at 256 entries in `RFPNotificationBroadcaster`, which means duplicate broadcasts could occur if an identical `ticket_id` is re-attempted after 256 intervening events.
2. Frontend fallback reconciliation on reconnection fetches a maximum of 50 tickets (`?limit=50`), potentially omitting older missed tickets during prolonged network drops without a manual page refresh.
3. Automated frontend tests in `rfpNotifications.test.ts` thoroughly test parsing, auth, and state logic but lack DOM component rendering tests for `RFPRealtimeNotificationBanner` and `RFPIntakePage`.
4. Specification metadata in `specs/034-sse-rfp-notifications/spec.md` remains in `Status: Draft`, and confirmation of test execution prior to merging into `main` is advised.

## Reproduction

1. **Server Deduplication Window Boundary**:
   - In `RFPNotificationBroadcaster`, publish `tkt_0001`.
   - Publish 256 subsequent distinct tickets (`tkt_0002` through `tkt_0257`).
   - Call `publish_ticket_created` with `tkt_0001` again.
   - *Result*: `tkt_0001` is published a second time because it was evicted from `_published_ticket_ids` (`maxlen=256`).
2. **Reconciliation Fetch Window**:
   - Disconnect the client SSE stream in `useRFPNotifications.ts`.
   - Register 60 new RFP tickets on the backend.
   - Reconnect the client stream; `reconcileMissedTickets` triggers `GET /api/v1/rfp/tickets?limit=50`.
   - *Result*: The first 10 tickets created during the disconnection window are omitted from the initial reconciliation merge until paginated.
3. **UI Component Test Coverage**:
   - Inspect `uis/backoffice/__tests__/rfpNotifications.test.ts`.
   - Observe that neither `RFPRealtimeNotificationBanner` nor `RFPIntakePage` is mounted in a JSDOM container with React `act()` or testing utilities.
4. **Diff Hygiene**:
   - Inspect `specs/034-sse-rfp-notifications/spec.md:7`.
   - Observe `**Status**: Draft`.

## Suspected Code Paths

- `services/api/infrastructure/messaging/rfp_notification_broadcaster.py:31` — `self._published_ticket_ids = deque(maxlen=max_history)` bounded ring buffer.
- `uis/backoffice/hooks/useRFPNotifications.ts:93` — `reconcileMissedTickets` hardcoded query `?limit=50`.
- `uis/backoffice/__tests__/rfpNotifications.test.ts` — Missing rendering tests for `RFPRealtimeNotificationBanner`.
- `uis/backoffice/components/rfp/RFPRealtimeNotificationBanner.tsx` — Target component for rendering tests.
- `specs/034-sse-rfp-notifications/spec.md:7` — Status header pending update from `Draft` to `Complete`.

## Root Cause Hypothesis

**Confidence: High**.
These findings represent deliberate or pragmatic scoping decisions rather than critical system failures:
- Bounded memory structures (`deque(maxlen=256)`) and REST query limits (`limit=50`) were implemented to prevent memory exhaustion and network saturation under high throughput in a single-instance environment. Client-side deduplication was explicitly built in `useRFPNotifications.ts` (`seenTicketIdsRef`) and `rfpNotificationsClient.ts` (`mergeAndDeduplicateTickets`) to serve as the second layer of defense.
- React Testing Library is not configured in `uis/backoffice/package.json` (the project relies on React 18 `createRoot` and `act` directly from `react-dom/client`), which led to prioritizing comprehensive protocol and client logic tests (`rfpNotifications.test.ts`).
- Spec status was preserved as `Draft` pending end-to-end verification and formal review before landing on `main`.

## Proposed Remediation

**Preferred**:
1. **Server Deduplication**: Keep `_published_ticket_ids` bounded or raise `max_history` default if needed, and document in the code docstrings that client-side deduplication guarantees idempotency even if server buffer eviction occurs.
2. **Reconciliation Window**: Keep `limit=50` (or raise to `limit=100`) and document that for disconnections spanning more than 50 tickets, pagination or full table refresh covers historical depth.
3. **UI Component Tests**: Add a dedicated component test file `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx` using the project's native `createRoot` + `act` pattern (as in `DepartmentApprovalPanel.test.tsx` and `rfp.test.tsx`) to verify banner rendering, metadata display, and dismissal.
4. **Diff Hygiene & Spec Status**: Update `specs/034-sse-rfp-notifications/spec.md` status from `Draft` to `Complete` (or `Implemented`), confirm `feature.json` points to `specs/034-sse-rfp-notifications`, and execute full verification (`pytest` and `npm test`).

**Alternatives**:
- *Redis Key-Value / TTL Deduplication*: For Part 2 multi-worker scaling, replace in-memory deque with Redis key expiration (`SET ticket:<id> EX 86400 NX`).

**Files likely to change**:
- `services/api/infrastructure/messaging/rfp_notification_broadcaster.py` (docstring clarification or history limit)
- `uis/backoffice/hooks/useRFPNotifications.ts` (reconciliation limit parameterization)
- `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx` (new test suite)
- `specs/034-sse-rfp-notifications/spec.md` (status update)

**Tests to add or update**:
- `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx`: Verify rendering of `RFPRealtimeNotificationBanner` with ticket metadata (`ticket_id`, `client_name`, `services_requested`) and dismiss button callback.
- `services/api/tests/test_rfp_sse_notifications.py`: Add an explicit test asserting broadcaster behavior when duplicate tickets exceed `max_history`.

## Risks & Considerations

- **Memory Consumption**: Expanding in-memory queues indefinitely would introduce memory leak vectors in long-running processes; maintaining bounded deques is sound architecture.
- **Test Environment Consistency**: Adding `@testing-library/react` might conflict with existing React 18 scripts and peer dependencies; using `createRoot` / `act` preserves zero added dependencies and matches existing test conventions.

## Open Questions

- None. All four items are clearly understood and actionable.
