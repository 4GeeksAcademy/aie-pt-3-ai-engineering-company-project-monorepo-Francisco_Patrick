# Quickstart & Validation Guide: Automated Nightly Telemetry Export & Orchestration

**Feature**: `022-nightly-telemetry-export` | **Branch**: `022-nightly-telemetry-export`
**Created**: 2026-10-27

---

## 1. Prerequisites & Environment Setup

Ensure you are located at the repository root and your virtual environment with monorepo dependencies is active:

```bash
# Verify Python version and database access
python -V
# Expected: Python 3.11+
```

---

## 2. Validation Scenarios

### Scenario 1: Autonomous Default Run (Preceding UTC Day)

Validates **FR-001, FR-002, FR-003, FR-007, and SC-001**:

```bash
# Execute nightly export without parameters (defaults to UTC yesterday)
python scripts/nightly_export.py
```

**Expected Results**:
1. Exit code is `0`.
2. Output confirms target date resolved to yesterday UTC.
3. File `data/raw/telemetry_<YESTERDAY>.csv` is created.
4. Downstream pipeline subprocess finishes with exit code `0`.
5. Database `job_runs` table has a new record with `status = 'completed'` and non-null `started_at` / `finished_at`.

---

### Scenario 2: Historical Backfill with Target Date Override

Validates **FR-002, FR-003, and User Story 3**:

```bash
# Via CLI argument
python scripts/nightly_export.py --date 2026-10-24

# Or via Environment Variable
TARGET_DATE=2026-10-24 python scripts/nightly_export.py
```

**Expected Results**:
1. Target date is pinned to `2026-10-24`.
2. Telemetry events for `2026-10-24` are extracted to `data/raw/telemetry_2026-10-24.csv`.
3. Downstream KPI pipeline executes for the window `2026-10-24T00:00:00Z` to `2026-10-24T23:59:59Z`.
4. `job_runs` records a `completed` entry for `(job_name='nightly_export', target_date='2026-10-24')`.

---

### Scenario 3: Concurrency Locking Verification

Validates **FR-005, SC-002, and User Story 2**:

Simulate overlapping runs by inserting a mock `processing` record or running two instances:

```python
# Quick scratch test in Python:
from services.jobs.models import JobRun, JobStatus, init_jobs_db
from services.jobs.runner import NightlyExportRunner
from data.pipelines.models import get_engine, get_session

engine = get_engine()
init_jobs_db(engine)

# Insert active processing lock
with get_session(engine) as session:
    active_run = JobRun(
        job_name="nightly_export",
        target_date="2026-10-25",
        status=JobStatus.PROCESSING,
    )
    session.add(active_run)
    session.commit()

# Execute runner: must detect lock, log INFO, and skip
runner = NightlyExportRunner(engine=engine)
result = runner.execute(target_date_override="2026-10-25")
assert result.skipped is True
assert result.skip_reason == "concurrency_lock_active"
```

**Expected Results**:
1. Secondary runner immediately aborts work.
2. Returns clean exit code `0`.
3. Emits `INFO` log stating an active process is running.
4. Zero duplicate CSV files or pipeline subprocesses spawned.

---

### Scenario 4: Idempotency & Duplicate Run Rejection

Validates **FR-006, SC-005, and User Story 3**:

```bash
# Re-run for an already-completed target date
python scripts/nightly_export.py --date 2026-10-24
```

**Expected Results**:
1. Exit code is `0`.
2. Emits `INFO` log: `Target date 2026-10-24 has already completed successfully. Skipping export.`
3. Existing file `data/raw/telemetry_2026-10-24.csv` is NOT modified or overwritten.
4. Downstream pipeline is NOT triggered.

---

### Scenario 5: Fault Resiliency & Clean State Recovery

Validates **FR-008, SC-003, and User Story 4**:

Run with a simulated failure (e.g., simulating downstream pipeline error):

```python
# Execute runner with an invalid pipeline path or simulate failure
runner = NightlyExportRunner(engine=engine)
# Trigger execution with simulated failure
result = runner.execute(...)
# Check job_runs table
```

**Expected Results**:
1. Exit code is `1`.
2. Status in `job_runs` transitions cleanly to `failed`.
3. `error_message` is populated with sanitized diagnostic summary (no passwords or credentials).
4. `finished_at` timestamp is set.
5. Exactly zero records remain in `processing` status.

---

## 3. Automated Test Suite Execution

Run the complete unit and integration test suite:

```bash
pytest tests/unit/jobs/ tests/integration/jobs/ -v
```
