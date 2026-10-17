# Tasks: Telemetry Report Endpoint & Operational Dashboard

**Input**: Design documents from `/specs/018-telemetry-report-endpoint/`  
**Prerequisites**: [plan.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/018-telemetry-report-endpoint/plan.md), [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/018-telemetry-report-endpoint/spec.md), [research.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/018-telemetry-report-endpoint/research.md), [data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/018-telemetry-report-endpoint/data-model.md), [contracts/](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/018-telemetry-report-endpoint/contracts/)  
**Tests**: Automated tests are specified for all backend pipeline functions, cache TTL, API endpoints, and frontend components per Constitution Principle VI.  
**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Include exact file paths in descriptions

## Path Conventions

- **Monorepo Shared**: `packages/shared/types/`
- **Backend Service (Analytics)**: `services/telemetry/`
- **Backend API (FastAPI)**: `services/api/`
- **Frontend Dashboard (Next.js)**: `uis/backoffice/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, cross-cutting contracts, and directory setup.

- [X] T001 [P] Create shared TypeScript telemetry interfaces in `packages/shared/types/telemetry.ts`
- [X] T002 Re-export telemetry types in `packages/shared/types/index.ts`
- [X] T003 [P] Create telemetry analysis package root in `services/telemetry/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data schemas, persistence adapters, and cache infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create Pydantic reporting domain models and response schemas in `services/api/domain/telemetry/report_models.py`
- [X] T005 [P] Implement thread-safe in-memory cache `TelemetryReportCache` with 60-second TTL in `services/api/application/telemetry/cache.py`
- [X] T006 [P] Implement raw telemetry event extraction query in `services/api/infrastructure/persistence/sqlmodel/telemetry_repo.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Operational System Health Telemetry Reporting with Caching (Priority: P1) 🎯 MVP

**Goal**: Expose `GET /telemetry/report` and `/api/v1/telemetry/report` in FastAPI to resolve a 7-day UTC reporting window (or custom date range), orchestrate metric calculation, and serve responses from a 60-second in-memory cache with `X-Cache` headers.

**Independent Test**: Request `GET /telemetry/report` without parameters and verify that a 7-day UTC period is resolved; re-request within 60 seconds with identical parameters and verify `X-Cache: HIT` is returned instantly without re-querying the data store; test date validation for inverted ranges returning 422.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [P] [US1] Create API integration and caching tests in `services/api/tests/api/test_telemetry_report.py`

### Implementation for User Story 1

- [X] T008 [US1] Implement report orchestration service in `services/api/application/telemetry/report_service.py`
- [X] T009 [US1] Implement `GET /telemetry/report` and `/api/v1/telemetry/report` endpoint with date validation and cache headers in `services/api/presentation/api/v1/telemetry.py`
- [X] T010 [US1] Register `TelemetryReportService` and cache provider dependencies in `services/api/presentation/dependencies.py`

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently (MVP ready with stubbed or initial metrics).

---

## Phase 4: User Story 2 - Temporal Operational Metrics Pipeline (Priority: P1)

**Goal**: Implement vectorized, side-effect-free Pandas metric functions in `services/telemetry/analysis.py` calculating daily event volume (`events_per_day`) and error distributions (`error_rate_by_type`) with mandatory UTC normalization before grouping.

**Independent Test**: Provide sample datasets to each metric calculation function with explicit start and end dates; verify that calling each function multiple times produces identical, deterministic output without procedural loops (`for`/`while`).

### Tests for User Story 2 ⚠️

- [X] T011 [P] [US2] Create unit tests for Pandas metric transformations and UTC normalization in `services/api/tests/unit/test_telemetry_analysis.py`

### Implementation for User Story 2

- [X] T012 [US2] Implement UTC datetime normalization and `calculate_events_per_day` in `services/telemetry/analysis.py`
- [X] T013 [US2] Implement vectorized error filtering and `calculate_error_rate_by_type` in `services/telemetry/analysis.py`
- [X] T014 [US2] Implement consolidated pipeline runner `generate_telemetry_report` in `services/telemetry/analysis.py`
- [X] T015 [US2] Connect analysis pipeline runner with database telemetry extractor in `services/api/application/telemetry/report_service.py`

**Checkpoint**: At this point, User Stories 1 AND 2 work together independently with live vectorized Pandas analytics.

---

## Phase 5: User Story 3 - Authentication Flow Reliability & Failure Rate Tracking (Priority: P2)

**Goal**: Add the third metric function `calculate_auth_failure_rate` in `services/telemetry/analysis.py` calculating the daily ratio of failed login attempts to total login attempts with safe division by zero, and include it under `auth_failure_rate` in the report payload.

**Independent Test**: Pass datasets with mixed successful and failed login attempts to `calculate_auth_failure_rate`; verify ratio calculation and that zero attempts safely evaluate to 0.0 without division-by-zero exceptions.

### Tests for User Story 3 ⚠️

- [X] T016 [P] [US3] Add unit tests for `calculate_auth_failure_rate` with zero-division scenarios in `services/api/tests/unit/test_telemetry_analysis.py`

### Implementation for User Story 3

- [X] T017 [US3] Implement `calculate_auth_failure_rate` with vectorized calculation and `.fillna(0.0)` in `services/telemetry/analysis.py`
- [X] T018 [US3] Wire `auth_failure_rate` into `generate_telemetry_report` and update report models in `services/telemetry/analysis.py`
- [X] T019 [US3] Add endpoint verification tests for `auth_failure_rate` in `services/api/tests/api/test_telemetry_report.py`

**Checkpoint**: At this point, User Stories 1, 2, and 3 are complete and independently verified.

---

## Phase 6: User Story 4 - Engineering Telemetry Visual Dashboard in Backoffice (Priority: P2)

**Goal**: Build a lightweight, accessible Next.js dashboard at `uis/backoffice/app/telemetry/page.tsx` rendering SVG/Tailwind charts and tables for daily event volume, error distribution, and authentication failure rate, with active period display, header navigation, and error resilience.

**Independent Test**: Navigate to `/telemetry` in Backoffice UI, verify active period display, chart/table components, and retry action on simulated API failure.

### Tests for User Story 4 ⚠️

- [X] T020 [P] [US4] Create frontend unit tests for telemetry dashboard in `uis/backoffice/__tests__/telemetry.test.tsx`

### Implementation for User Story 4

- [X] T021 [P] [US4] Implement daily event volume SVG bar chart component in `uis/backoffice/components/telemetry/EventVolumeChart.tsx`
- [X] T022 [P] [US4] Implement error distribution table and progress bar component in `uis/backoffice/components/telemetry/ErrorDistribution.tsx`
- [X] T023 [P] [US4] Implement authentication reliability metric card component in `uis/backoffice/components/telemetry/AuthFailureCard.tsx`
- [X] T024 [US4] Build engineering telemetry dashboard page with period controls and retry states in `uis/backoffice/app/telemetry/page.tsx`
- [X] T025 [US4] Add Telemetry navigation link in `uis/backoffice/components/Header.tsx`

**Checkpoint**: All user stories are now independently functional across backend and frontend.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Static analysis, type checking, test suite verification, and end-to-end scenario validation.

- [X] T026 [P] Execute workspace TypeScript type checking (`npm run typecheck`) across `packages/shared` and `uis/backoffice`
- [X] T027 [P] Execute backend test suite (`pytest`) across unit and API tests in `services/api`
- [X] T028 Execute end-to-end quickstart validation scenarios in `specs/018-telemetry-report-endpoint/quickstart.md`
- [X] T029 Update OpenAPI schema and contract definitions in `specs/018-telemetry-report-endpoint/contracts/telemetry-report-api.yaml`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion - BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) completion.
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) completion (can proceed in parallel with US1).
- **User Story 3 (Phase 5)**: Depends on User Story 2 (Phase 4) completion for pipeline function integration.
- **User Story 4 (Phase 6)**: Depends on User Story 1 (Phase 3) API contracts and Phase 1 shared types.
- **Polish (Phase 7)**: Depends on all user story phases being completed.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories (can use stub or initial metrics).
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Implements core vectorized Pandas metrics.
- **User Story 3 (P2)**: Extends User Story 2 pipeline with authentication failure rates.
- **User Story 4 (P2)**: Consumes User Story 1 endpoint via shared contracts.

### Within Each User Story

- Tests MUST be written and fail before implementing feature code.
- Models and schemas before service logic.
- Service logic before endpoint / UI presentation.
- Story complete and verified before moving to next priority.

### Parallel Opportunities

- Setup tasks `T001` and `T003` can run in parallel.
- Foundational tasks `T004`, `T005`, and `T006` can run in parallel.
- Once Foundational phase is complete, US1 and US2 can proceed in parallel.
- In US4, subcomponents `T021`, `T022`, and `T023` can be developed in parallel.
- Validation tasks `T026` and `T027` can run in parallel.

---

## Parallel Execution Examples

### User Story 1 (API & Cache)
```bash
# Write test first:
Task: T007 [P] [US1] Create API integration and caching tests in services/api/tests/api/test_telemetry_report.py
```

### User Story 2 (Pandas Analytics Pipeline)
```bash
# Write test first:
Task: T011 [P] [US2] Create unit tests for Pandas metric transformations and UTC normalization in services/api/tests/unit/test_telemetry_analysis.py
```

### User Story 4 (Backoffice Dashboard Components)
```bash
# Launch component development in parallel:
Task: T021 [P] [US4] Implement daily event volume SVG bar chart component in uis/backoffice/components/telemetry/EventVolumeChart.tsx
Task: T022 [P] [US4] Implement error distribution table and progress bar component in uis/backoffice/components/telemetry/ErrorDistribution.tsx
Task: T023 [P] [US4] Implement authentication reliability metric card component in uis/backoffice/components/telemetry/AuthFailureCard.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 & Initial Metrics)
1. Complete Phase 1: Setup (`T001`-`T003`).
2. Complete Phase 2: Foundational (`T004`-`T006`).
3. Complete Phase 3: User Story 1 (`T007`-`T010`).
4. **STOP and VALIDATE**: Test `GET /telemetry/report` independently with curl and pytest.

### Incremental Delivery
1. Deliver US1 (Endpoint & In-Memory Cache).
2. Deliver US2 (Vectorized Pandas Analysis Pipeline for Volume & Errors).
3. Deliver US3 (Authentication Reliability Metrics).
4. Deliver US4 (Backoffice Engineering Visual Dashboard).
5. Run Phase 7 Polish & Validation gates.
