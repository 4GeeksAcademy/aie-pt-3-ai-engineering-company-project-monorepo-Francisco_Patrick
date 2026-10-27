# Service Contract: Nightly Export Orchestrator (`services/jobs/`)

**Feature**: `022-nightly-telemetry-export` | **Branch**: `022-nightly-telemetry-export`
**Created**: 2026-10-27

---

## 1. Module Structure & Exports

The `services/jobs/` package encapsulates all persistence models, locking semantics, CSV exporting logic, and subprocess invocation.

```text
services/jobs/
├── __init__.py          # Exports NightlyExportRunner, JobRun, JobStatus, init_jobs_db
├── models.py            # SQLModel entities (JobRun), enums (JobStatus)
└── runner.py            # NightlyExportRunner service implementation
```

---

## 2. API Specifications

### 2.1 Enum: `JobStatus`

```python
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 2.2 Dataclass / Result Object: `JobExecutionResult`

```python
@dataclass(frozen=True)
class JobExecutionResult:
    status: JobStatus
    target_date: str
    run_id: Optional[UUID] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    csv_path: Optional[str] = None
    pipeline_exit_code: Optional[int] = None
    error_message: Optional[str] = None
```

### 2.3 Class: `NightlyExportRunner`

```python
class NightlyExportRunner:
    def __init__(
        self,
        engine: Optional[Engine] = None,
        raw_data_dir: Optional[str] = None,
        job_name: str = "nightly_export",
    ) -> None:
        """Initialize orchestrator with database engine and export directory."""
        ...

    def resolve_target_date(self, override: Optional[str] = None) -> str:
        """Resolve date string in YYYY-MM-DD UTC format from override, env, or UTC yesterday.
        
        Raises:
            ValueError: If target date format is invalid.
        """
        ...

    def check_active_lock(self) -> Optional[JobRun]:
        """Check if an active processing job currently exists."""
        ...

    def check_idempotency(self, target_date: str) -> Optional[JobRun]:
        """Check if target_date has already completed successfully."""
        ...

    def export_telemetry_csv(self, target_date: str) -> str:
        """Export telemetry events for target_date to data/raw/telemetry_YYYY-MM-DD.csv.
        
        Returns:
            Path to exported CSV file.
        """
        ...

    def run_downstream_pipeline(self, target_date: str) -> subprocess.CompletedProcess:
        """Execute downstream pipeline subprocess for target_date."""
        ...

    def execute(self, target_date_override: Optional[str] = None, dry_run: bool = False) -> JobExecutionResult:
        """Execute end-to-end nightly export orchestration cycle."""
        ...
```
