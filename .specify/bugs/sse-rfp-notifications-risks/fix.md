# Bug Fix: Minor Risks and Review Observations in Real-Time SSE RFP Notifications

- **Slug**: sse-rfp-notifications-risks
- **Fixed**: 2026-11-24T16:03:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Addressed review observations across server deduplication memory bounds, REST reconciliation limit configurability, React UI component testing for SSE banners, and specification lifecycle metadata hygiene.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/infrastructure/messaging/rfp_notification_broadcaster.py` | modified | Documented bounded ring buffer (`deque(maxlen=max_history)`) rationale and layered client-side deduplication defense. |
| `services/api/tests/test_rfp_sse_notifications.py` | modified | Added `test_broadcaster_deduplication_exceeding_max_history` verifying bounded eviction and re-publication behavior. |
| `uis/backoffice/hooks/useRFPNotifications.ts` | modified | Added `reconciliationLimit` option defaulting to 100 with fallback pagination documentation. |
| `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx` | added | Added native `createRoot` + `act` unit tests covering all connection states, retry actions, arrival details, and dismissal. |
| `specs/034-sse-rfp-notifications/spec.md` | modified | Updated status from `Draft` to `Complete`. |

## Diff Highlights

```python
# services/api/infrastructure/messaging/rfp_notification_broadcaster.py
# Documenting layered defense:
Note on bounded server deduplication:
Server deduplication is bounded to `max_history` items to prevent unbounded memory growth in
long-running processes. Even if a ticket ID evicts from the broadcaster's ring buffer after
`max_history` subsequent events, client-side deduplication (`seenTicketIdsRef` in `useRFPNotifications`
and `mergeAndDeduplicateTickets` in `rfpNotificationsClient`) provides a secondary layer of defense
guaranteeing idempotency in the UI.
```

```typescript
// uis/backoffice/hooks/useRFPNotifications.ts
export interface UseRFPNotificationsOptions {
  apiUrl?: string;
  statusFilter?: string;
  reconciliationLimit?: number;
  onTicketsReceived?: (incomingTickets: IntakeTicketSummaryDTO[]) => void;
}

const reconciliationLimit = options.reconciliationLimit ?? 100;
const response = await fetch(
  `${apiUrl.replace(/\/$/, '')}/api/v1/rfp/tickets?limit=${reconciliationLimit}`,
  { method: 'GET', headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
);
```

```markdown
<!-- specs/034-sse-rfp-notifications/spec.md -->
-**Status**: Draft
+**Status**: Complete
```

## Tests Added or Updated

- `services/api/tests/test_rfp_sse_notifications.py::test_broadcaster_deduplication_exceeding_max_history` — Confirms bounded eviction after `max_history` events allows re-publication at broadcaster layer, delegating UI-level idempotency to client deduplication.
- `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx::renders connected badge with positive health indicators` — Pins down connected state badge rendering.
- `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx::renders reconnecting state with attempt counter and handles manual retry click` — Pins down reconnect attempt counter and manual retry trigger.
- `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx::renders unauthorized and connecting badges accordingly` — Pins down unauthorized and connecting states.
- `uis/backoffice/__tests__/RFPRealtimeNotificationBanner.test.tsx::renders arrival banner with ticket details and triggers dismiss callback` — Pins down real-time arrival toast attributes and dismissal callback.

## Local Verification

- Commands run:
  - `python -m pytest services/api/tests/test_rfp_sse_notifications.py` → 9 passed in 4.43s
  - `npm test -- RFPRealtimeNotificationBanner.test.tsx rfpNotifications.test.ts` → 2 test suites passed, 12 tests passed
  - `npm run typecheck` (`tsc --noEmit`) → 0 type errors across `uis/backoffice`
- Manual checks:
  - Validated adherence to strict TypeScript typing rule (zero `any`, explicit typing, strict imports).

## Deviations from Assessment

None. All four recommendations from the assessment were applied as specified.

## Follow-ups

- For Phase 2 (multi-worker deployment), consider Redis-backed key expiration (`SET ticket:<id> EX 86400 NX`) to replace in-memory process deduplication.
