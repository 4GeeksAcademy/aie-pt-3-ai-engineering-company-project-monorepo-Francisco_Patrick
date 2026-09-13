# Tasks: Comprehensive Error Handling

**Input**: Design documents from `/specs/008-error-handling/`

**Prerequisites**: [`plan.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/plan.md), [`spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/spec.md), [`research.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/research.md), [`data-model.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/data-model.md), [`contracts/`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/contracts/)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Define error data models and shared API error interfaces.

- [x] T001 Define centralized error types and API error handling interfaces in `uis/backoffice/lib/api.ts`
- [x] T002 Define backend structured error response models (`ErrorResponsePayload`) in `services/api/domain/exceptions.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure fixes required before story implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Fix public route registration in `uis/backoffice/components/AuthGuard.tsx` to include `/forgot-password` and `/reset-password` in `PUBLIC_PATHS`
- [x] T004 Enhance `fetchWithAuth` in `uis/backoffice/lib/api.ts` with network try/catch block and structured re-throw

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Resilient Frontend Data Fetching & 3-State UI (Priority: P1) 🎯 MVP

**Goal**: Implement 3-state UI pattern (loading, data, error with retry CTA) and safe rendering fallbacks across all frontend components.

**Independent Test**: Disconnect network or force API failure while loading Suppliers, Incidents, and Profile views. Verify loading skeleton appears, cleared by `finally`, error banner renders with human-readable explanation and Retry CTA.

- [x] T005 [P] [US1] Implement 3-state UI pattern and `finally` loading cleanup in `uis/backoffice/app/suppliers/page.tsx`
- [x] T006 [P] [US1] Add explicit `catch` handler to `handleAddSupplier` in `uis/backoffice/app/suppliers/page.tsx`
- [x] T007 [P] [US1] Add interactive Retry CTA button to error banner in `uis/backoffice/app/suppliers/page.tsx`
- [x] T008 [P] [US1] Implement 3-state UI pattern, Retry CTA button, and `finally` cleanup in `uis/backoffice/app/account/profile/page.tsx`
- [x] T009 [P] [US1] Implement optional chaining (`?.`) and safe default fallbacks across login and registration forms in `uis/backoffice/app/login/page.tsx` and `uis/backoffice/app/register/page.tsx`
- [x] T010 [P] [US1] Add console error logging in catch blocks of `uis/backoffice/app/login/page.tsx` and `uis/backoffice/app/register/page.tsx`
- [x] T011 [P] [US1] Ensure form submission failures handle status feedback cleanly in `uis/website/app/components/home/ApplicationForm.tsx`

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Secure & Structured Backend API Error Handling (Priority: P2)

**Goal**: Ensure backend routes return structured JSON error payloads with correct HTTP status codes (400, 404, 422, 500) and zero sensitive data exposure or raw Python stack trace dumps.

**Independent Test**: Submit malformed payloads and force runtime failures on `/api/incidents/analyze`, `/suppliers`, and `/auth/forgot-password`. Verify response is clean JSON without internal paths or raw Python `str(e)`.

- [x] T012 [P] [US2] Refactor `/api/incidents/analyze` in `services/api/main.py` to use granular try/except blocks and user-safe 500 error messages
- [x] T013 [P] [US2] Wrap TinyDB operations in `services/api/routes/suppliers.py` with try/except blocks returning structured HTTP 500/503 responses
- [x] T014 [P] [US2] Sanitize console log outputs in `services/api/application/services/email_service.py` to mask user email PII and omit raw password reset URL tokens
- [x] T015 [P] [US2] Add try/except error handling to Resend API dispatch in `services/api/application/services/email_service.py`
- [x] T016 [P] [US2] Mask plaintext email addresses in audit log detail strings in `services/api/application/services/auth_service.py`
- [x] T017 [P] [US2] Add try/except error handling around email dispatch call in `services/api/application/services/auth_service.py`
- [x] T018 [P] [US2] Map `ValueError` exceptions to structured JSON response payloads in `services/api/presentation/api/profile_routes.py` and `services/api/presentation/api/user_routes.py`

**Checkpoint**: User Story 2 is fully functional and testable independently.

---

## Phase 5: User Story 3 - Robust & Safe Python CLI Script Execution (Priority: P3)

**Goal**: Ensure Python CLI scripts wrap file I/O and CSV operations in try/except blocks, output diagnostic text to `sys.stderr`, and issue standard non-zero exit codes on failure or interruption.

**Independent Test**: Run `scripts/analyze.py` with missing/corrupted files or press Ctrl+C during `scripts/seed_incidents.py`. Verify stderr output and non-zero exit code (`1` or `130`).

- [x] T019 [P] [US3] Wrap file writing in `export_to_csv` within `scripts/analyze.py` in try/except block with stderr error logging
- [x] T020 [P] [US3] Replace `except KeyboardInterrupt: pass` in `scripts/analyze.py` with stderr logging and `sys.exit(130)`
- [x] T021 [P] [US3] Add per-record try/except error handling inside CSV loop in `scripts/seed_incidents.py` to log bad records to stderr and skip safely
- [x] T022 [P] [US3] Replace generic `except Exception as e:` in `main()` of `scripts/seed_incidents.py` with specific exception handling and explicit `sys.exit(1)`
- [x] T023 [P] [US3] Wrap database seeding in `services/api/seed.py` with try/except error handling and explicit `sys.exit(1)` on error

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Codebase audit and verification.

- [x] T024 [P] Audit codebase for remaining raw `print` or `console.error` statements exposing sensitive internal paths or credentials
- [x] T025 Execute end-to-end quickstart validation scenarios documented in `specs/008-error-handling/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion. User stories can proceed in parallel or priority order (US1 → US2 → US3).
- **Polish (Phase 6)**: Depends on completion of user stories.

### Parallel Opportunities
- T005, T006, T007, T008, T009, T010, T011 in User Story 1 can run in parallel.
- T012, T013, T014, T015, T016, T017, T018 in User Story 2 can run in parallel.
- T019, T020, T021, T022, T023 in User Story 3 can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Frontend 3-State UI & Recovery)
4. Validate User Story 1 independently via Quickstart Guide.
