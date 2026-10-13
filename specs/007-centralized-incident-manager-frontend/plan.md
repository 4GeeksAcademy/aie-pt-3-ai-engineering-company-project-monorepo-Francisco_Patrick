# Implementation Plan: Centralized Incident Manager - Frontend

**Branch**: `007-centralized-incident-manager-frontend` | **Date**: 2026-09-13 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/007-centralized-incident-manager-frontend/spec.md)

**Input**: Feature specification from `/specs/007-centralized-incident-manager-frontend/spec.md`

## Summary

Build and integrate the Centralized Incident Manager frontend UI components within `uis/backoffice` (Next.js / React) and extract shared TypeScript schemas/validation logic into `packages/shared/`. The frontend will feature a client-validated incident registration page with visual branch highlighting, an incident listing panel with multi-attribute filters (`status`, `origin`, `branch`) and inline status updates with visual rollback on failure, and an operational summary metrics panel resilient to API timeouts and 500 errors.

## Technical Context

**Language/Version**: TypeScript 5.9 / Node.js 20+

**Primary Dependencies**: Next.js 14 (App Router / Pages), React 18, TailwindCSS 4

**Storage**: Local state / React hooks / FastAPI Backend (`/api/incidents`)

**Testing**: React Testing Library / Jest / Playwright

**Target Platform**: Modern Web Browsers (Chrome, Edge, Firefox, Safari)

**Project Type**: Monorepo Web Application (`uis/backoffice`, `packages/shared`)

**Performance Goals**: Client-side validation <10ms; initial page render <300ms; instant visual status revert on API error

**Constraints**: Zero stack traces or raw technical error dumps shown to end-users; mandatory visual branch highlighting when `origin === 'branch'`; graceful error boundary isolation per panel

**Scale/Scope**: ~3 screens/components (`IncidentRegistrationForm`, `IncidentListPanel`, `IncidentSummaryPanel`), shared validation layer in `packages/shared`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Shared Package Reusability**: Validation and types are extracted into `packages/shared/` for cross-cutting monorepo consumption. (PASSED)
- **User-Friendly Error Handling**: Zero raw technical server text/stack traces; all errors mapped to plain language. (PASSED)
- **Resilient Layout Isolation**: Summary panel or listing failures do not crash adjacent UI components. (PASSED)

## Project Structure

### Documentation (this feature)

```text
specs/007-centralized-incident-manager-frontend/
├── plan.md              # Implementation Plan
├── research.md          # Technical decisions and trade-offs
├── data-model.md        # Shared data types and form models
├── quickstart.md        # Step-by-step verification guide
├── contracts/
│   └── management-ui.md # Component props and API client interfaces
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
packages/shared/
├── types/
│   └── incidents.ts     # Incident, IncidentStatus, IncidentCategory, IncidentOrigin, IncidentMetrics interfaces
└── validation/
    └── incidents.ts     # Client & shared validation rules

uis/backoffice/
├── app/
│   ├── incidents/
│   │   ├── page.tsx     # Incident Management Dashboard (List + Summary)
│   │   └── register/
│   │       └── page.tsx # Incident Registration Page
├── components/
│   ├── incidents/
│   │   ├── IncidentRegistrationForm.tsx
│   │   ├── IncidentListPanel.tsx
│   │   ├── IncidentSummaryPanel.tsx
│   │   └── BranchSelect.tsx
│   └── Navigation.tsx
└── lib/
    └── api/
        └── incidents.ts # API fetch client wrappers with error mapping
```

**Structure Decision**: Standard monorepo layout placing shared validation and contracts in `packages/shared` and Next.js frontend pages/components in `uis/backoffice`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
