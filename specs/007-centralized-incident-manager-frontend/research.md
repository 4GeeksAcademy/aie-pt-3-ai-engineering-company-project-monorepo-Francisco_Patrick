# Phase 0 Research: Centralized Incident Manager - Frontend

## Decision 1: Extracted Shared Validation & Types (`packages/shared`)
- **Decision**: Place TypeScript incident interfaces (`Incident`, `IncidentCategory`, `IncidentStatus`, `IncidentOrigin`, `IncidentCreateInput`, `IncidentMetrics`) and client-side validation logic in `packages/shared/types/incidents.ts` and `packages/shared/validation/incidents.ts`.
- **Rationale**: Meets requirement "The validation logic from the previous project is extracted into `packages/shared/` and reused... without duplication."
- **Alternatives Considered**: Duplicating validation logic in `uis/backoffice` — rejected because it violates monorepo shared logic guidelines and cross-cutting requirements.

## Decision 2: Visual Branch Highlighting when Origin = Branch
- **Decision**: Dynamically apply distinct CSS styling (e.g. amber/orange border glow `border-amber-500 bg-amber-50/20` and prominent location badge) to the `branch` select component when `origin === 'branch'`.
- **Rationale**: Direct user requirement: "When `origin` is `branch`, the `branch` field is visually highlighted to remind the user they are reporting from a specific location."
- **Alternatives Considered**: Tooltip notice only — rejected because spec demands visual field highlighting.

## Decision 3: Inline List Status Update with Automatic Rollback
- **Decision**: Track previous status value per incident item during inline dropdown change. Trigger `PATCH /api/incidents/{id}/status`. If API returns an error or fails, revert state variable to previous status and emit user notification banner.
- **Rationale**: Enforces spec acceptance criteria: "Each incident allows updating its status directly from the list. If the update fails, the visual state reverts to the previous value and the user is notified."
- **Alternatives Considered**: Reloading whole page — rejected because it disrupts scrolling context and user experience.

## Decision 4: Resilient Summary & Listing Error Boundaries
- **Decision**: Wrap Incident Listing Panel, Registration Form, and Summary Metrics Panel in independent error boundary containers and localized error states (`isError`, `retry()`).
- **Rationale**: Guarantees that if `/api/incidents/summary` fails (e.g. 500 error or timeout), the Summary Panel displays a friendly retry card while Registration Form and Incident Listing Panel remain fully functional.
