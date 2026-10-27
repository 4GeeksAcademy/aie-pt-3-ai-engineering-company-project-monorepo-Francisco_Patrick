# Tasks: Automated Nightly Telemetry Export & Orchestration

**Input**: Design documents from `/specs/022-nightly-telemetry-export/`  
**Prerequisites**: [plan.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/plan.md), [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/spec.md), [data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/data-model.md), [research.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/research.md), [contracts/](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/contracts/), [quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/022-nightly-telemetry-export/quickstart.md)

---

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Every task includes an explicit, unambiguous file path.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, folder structure, and dependency verification

- [X] T001 Create directory structure for job runner and test suites in services/jobs/, tests/unit/jobs/, tests/integration/jobs/, and data/raw/
- [X] T002 [P] Initialize package export stubs and __init__.py files in services/jobs/__init__.py, tests/unit/jobs/__init__.py, and tests/integration/jobs/__init__.py
- [X] T003 [P] Verify Python 3.11+, SQLModel, SQLAlchemy, Pandas, Prefect 3.x, and pytest dependencies in services/api/requirements.txt and data/pipelines/README.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core DTOs, database models, table initialization, and error sanitization utilities

**⚠️ CRITICAL**: No user story implementation can begin until this foundational phase is complete

- [X] T004 [P] Implement JobStatus enum and JobExecutionResult dataclass in services/jobs/models.py
- [X] T005 [P] Implement JobRun SQLModel entity with table name job_runs and composite indexes idx_job_runs_name_target_date and idx_job_runs_name_status in services/jobs/models.py
- [X] T006 Implement init_jobs_db helper to safely inspect and create job_runs table in services/jobs/models.py
- [X] T007 [P] Implement sanitize_error_message utility masking credentials and truncating to 500 characters in services/jobs/runner.py

**Checkpoint**: Foundation ready — database entities and basic primitives ready for user story implementation.

---

## Phase 3: User Story 1 - Autonomous Daily Orchestration & Pipeline Execution (Priority: P1) 🎯 MVP

**Goal**: Deliver autonomous extraction of the preceding UTC day's telemetry events into `data/raw/telemetry_YYYY-MM-DD.csv`, trigger the downstream KPI pipeline subprocess (`data/pipelines/pipeline.py`), and record the completed execution lifecycle in `job_runs` via CLI `scripts/nightly_export.py`.

**Independent Test**: Trigger `python scripts/nightly_export.py` in an environment with telemetry events. Verify `data/raw/telemetry_YYYY-MM-DD.csv` is created with standard headers, the downstream KPI pipeline finishes successfully with exit code 0, and `job_runs` records a `completed` row with non-null start and finish timestamps.

### Tests for User Story 1

- [X] T008 [P] [US1] Unit test for telemetry CSV extraction and empty-state header writing in tests/unit/jobs/test_nightly_export_runner.py
- [X] T009 [P] [US1] Unit test for downstream pipeline subprocess execution arguments and return code handling in tests/unit/jobs/test_nightly_export_runner.py

### Implementation for User Story 1

- [X] T010 [US1] Implement export_telemetry_csv querying telemetry_events and writing snapshot to data/raw/telemetry_YYYY-MM-DD.csv in services/jobs/runner.py
- [X] T011 [US1] Implement run_downstream_pipeline invoking data/pipelines/pipeline.py via subprocess.run with target date parameters in services/jobs/runner.py
- [X] T012 [US1] Implement core orchestration lifecycle in NightlyExportRunner.execute creating processing record and transitioning to completed in services/jobs/runner.py
- [X] T013 [US1] Implement autonomous CLI entry point with --dry-run and --verbose flags, standard logging, and exit code 0 in scripts/nightly_export.py
- [X] T014 [US1] Integration test verifying end-to-end export, pipeline subprocess execution, and job_runs completion in tests/integration/jobs/test_nightly_export_e2e.py

**Checkpoint**: User Story 1 (MVP) is fully functional and delivers autonomous daily orchestration and pipeline execution.

---

## Phase 4: User Story 2 - Concurrency Locking & Duplicate Run Prevention (Priority: P1)

**Goal**: Prevent overlapping or concurrent executions of `nightly_export` using database-backed lock checks on active `processing` rows in `job_runs`, cleanly aborting duplicate runs with exit code 0 and logging at `INFO` level.

**Independent Test**: Launch the export runner when an active `processing` job exists. Verify the second instance detects the active lock, skips execution immediately with reason `concurrency_lock_active`, emits an `INFO` log, and exits cleanly with code 0 without writing files or invoking the pipeline subprocess.

### Tests for User Story 2

- [X] T015 [P] [US2] Unit test for check_active_lock and concurrency lock abort behavior in tests/unit/jobs/test_nightly_export_runner.py

### Implementation for User Story 2

- [X] T016 [US2] Implement atomic check_active_lock querying for active processing status for job_name in services/jobs/runner.py
- [X] T017 [US2] Wire concurrency lock check into NightlyExportRunner.execute to return skipped result when active lock is detected in services/jobs/runner.py
- [X] T018 [US2] Handle concurrency lock skip cleanly in CLI entry point with INFO log and exit code 0 in scripts/nightly_export.py
- [X] T019 [US2] Integration test verifying simulated concurrent execution race and single-instance lock acquisition in tests/integration/jobs/test_nightly_export_e2e.py

**Checkpoint**: Concurrency locking guarantees zero overlapping executions and eliminates duplicate processing.

---

## Phase 5: User Story 3 - Per-Day Idempotency & Historical Re-runs (Priority: P1)

**Goal**: Enforce strict per-day idempotency by checking for `completed` records for `(job_name, target_date)`, preserving existing audit CSV files, and supporting target date overrides via `TARGET_DATE` environment variable and `--date` CLI flag.

**Independent Test**: Re-run the export for a target date with an existing `completed` job run. Verify runner skips export and pipeline execution, logs skip, and leaves existing CSV untouched. Re-run with `--date YYYY-MM-DD` and verify historical date override behavior.

### Tests for User Story 3

- [X] T020 [P] [US3] Unit test for UTC date resolution (yesterday default, TARGET_DATE env, CLI override, and format validation) in tests/unit/jobs/test_nightly_export_runner.py
- [X] T021 [P] [US3] Unit test for check_idempotency and CSV snapshot preservation in tests/unit/jobs/test_nightly_export_runner.py

### Implementation for User Story 3

- [X] T022 [US3] Implement resolve_target_date supporting ISO format validation, TARGET_DATE env var, and UTC yesterday default in services/jobs/runner.py
- [X] T023 [US3] Implement check_idempotency checking existing completed status for (job_name, target_date) in services/jobs/runner.py
- [X] T024 [US3] Add file preservation guard in export_telemetry_csv to preserve existing snapshots without overwriting in services/jobs/runner.py
- [X] T025 [US3] Wire --date CLI argument and TARGET_DATE environment variable override into scripts/nightly_export.py
- [X] T026 [US3] Integration test verifying re-run idempotency, duplicate skipping, and historical backfill date override in tests/integration/jobs/test_nightly_export_e2e.py

**Checkpoint**: Per-day idempotency and backfill capabilities verified with zero data corruption.

---

## Phase 6: User Story 4 - Fault Resiliency & Clean State Recovery (Priority: P2)

**Goal**: Catch all runtime exceptions and subprocess non-zero exits, sanitize diagnostic messages, transition `job_runs` status cleanly to `failed` with `finished_at`, and exit with code 1, leaving zero records stranded in `processing`.

**Independent Test**: Trigger execution with a simulated export failure or non-zero subprocess exit code. Verify job status transitions to `failed`, error message is sanitized, exit code is 1, and no record remains in `processing`.

### Tests for User Story 4

- [X] T027 [P] [US4] Unit test for error handling, credential sanitization, and state recovery in tests/unit/jobs/test_nightly_export_runner.py
- [X] T028 [P] [US4] Unit test for malformed date string validation failure and clean abort in tests/unit/jobs/test_nightly_export_runner.py

### Implementation for User Story 4

- [X] T029 [US4] Wrap NightlyExportRunner.execute in robust try...except...finally block transitioning record to failed and recording sanitized diagnostic in services/jobs/runner.py
- [X] T030 [US4] Implement CLI non-zero exit code handling and error logging in scripts/nightly_export.py
- [X] T031 [US4] Integration test verifying failure recovery, lock clearance, and non-zero exit code in tests/integration/jobs/test_nightly_export_e2e.py

**Checkpoint**: System is resilient against all execution failures and guarantees zero orphaned locks.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Operational documentation, cron trigger configuration, and end-to-end quickstart validation

- [X] T032 [P] Document production cron schedule (0 2 * * *), log rotation, and environment configuration in data/pipelines/README.md
- [X] T033 [P] Update package exports and docstrings in services/jobs/__init__.py
- [X] T034 Execute full unit and integration test suite via pytest tests/unit/jobs/ tests/integration/jobs/ -v
- [X] T035 Execute validation scenarios from quickstart.md (Scenario 1 through Scenario 5) to confirm zero regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS all user stories.
- **User Stories (Phases 3-6)**: All depend on Foundational (Phase 2) completion.
  - Can proceed sequentially in priority order (US1 → US2 → US3 → US4) or in parallel where independent.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories. Serves as MVP.
- **User Story 2 (P1)**: Extends US1 runner lifecycle with concurrency lock checks — Can start after Phase 2, integrates with US1 runner.
- **User Story 3 (P1)**: Extends US1 runner lifecycle with idempotency checks and date resolution — Can start after Phase 2, integrates with US1 runner.
- **User Story 4 (P2)**: Hardens US1/US2/US3 runner lifecycle with error capture, credential masking, and guaranteed lock release — Depends on core runner implementation.

### Within Each User Story

- Unit tests written first, verified to fail before implementation.
- Models and utilities before service orchestration methods.
- Service runner logic before CLI wrapper integration.
- Integration tests verify end-to-end user story fulfillment.

### Parallel Opportunities

- **Phase 1 (Setup)**: T002 and T003 can execute in parallel.
- **Phase 2 (Foundational)**: T004, T005, and T007 can execute in parallel.
- **Phase 3 (User Story 1)**: Tests T008 and T009 can execute in parallel.
- **Phase 4 (User Story 2)**: Test T015 can run in parallel with US1 tasks.
- **Phase 5 (User Story 3)**: Tests T020 and T021 can run in parallel.
- **Phase 6 (User Story 4)**: Tests T027 and T028 can run in parallel.
- **Phase 7 (Polish)**: Documentation T032 and exports T033 can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 in parallel:
Task: "Unit test for telemetry CSV extraction and empty-state header writing in tests/unit/jobs/test_nightly_export_runner.py"
Task: "Unit test for downstream pipeline subprocess execution arguments and return code handling in tests/unit/jobs/test_nightly_export_runner.py"

# Implement core modules:
Task: "Implement export_telemetry_csv querying telemetry_events and writing snapshot to data/raw/telemetry_YYYY-MM-DD.csv in services/jobs/runner.py"
Task: "Implement run_downstream_pipeline invoking data/pipelines/pipeline.py via subprocess.run with target date parameters in services/jobs/runner.py"
```

---

## Parallel Example: User Story 3

```bash
# Launch date resolution and idempotency tests in parallel:
Task: "Unit test for UTC date resolution (yesterday default, TARGET_DATE env, CLI override, and format validation) in tests/unit/jobs/test_nightly_export_runner.py"
Task: "Unit test for check_idempotency and CSV snapshot preservation in tests/unit/jobs/test_nightly_export_runner.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T001` - `T003`).
2. Complete Phase 2: Foundational (`T004` - `T007`) — **CRITICAL**: Blocks all user stories.
3. Complete Phase 3: User Story 1 (`T008` - `T014`).
4. **STOP and VALIDATE**: Run `python scripts/nightly_export.py` to verify CSV snapshot creation, pipeline subprocess triggering, and `job_runs` completion.
5. Deployable MVP increment ready!

### Incremental Delivery

1. **Increment 1 (MVP)**: Setup + Foundational + User Story 1 → Basic autonomous nightly export and pipeline orchestration.
2. **Increment 2**: Add User Story 2 (Concurrency Locking) → Overlapping cron runs safely skipped.
3. **Increment 3**: Add User Story 3 (Per-Day Idempotency & Backfill) → Safe retries and historical date overrides.
4. **Increment 4**: Add User Story 4 (Fault Resiliency & State Recovery) → Zero orphaned locks and sanitized diagnostics.
5. **Increment 5**: Polish + Documentation + Quickstart verification.

---

## Notes

- Every task strictly adheres to `- [ ] [TaskID] [P?] [Story?] Description with file path`.
- Persistence and domain logic are encapsulated in `services/jobs/`, while the CLI entry point resides in `scripts/nightly_export.py`, adhering to Constitution Principle I and FR-009.
- Subprocess execution cleanly isolates the Prefect pipeline from the caller, adhering to FR-007.
- Existing telemetry assets (`services/telemetry/analysis.py` and `telemetry_events` table) remain 100% untouched.
