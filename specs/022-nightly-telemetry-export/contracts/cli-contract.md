# Interface Contract: Nightly Export CLI (`scripts/nightly_export.py`)

**Feature**: `022-nightly-telemetry-export` | **Branch**: `022-nightly-telemetry-export`
**Created**: 2026-10-27

---

## 1. CLI Overview & Execution Signature

The CLI entry point `scripts/nightly_export.py` runs as an autonomous, detached process outside the application web server threads.

```bash
python scripts/nightly_export.py [OPTIONS]
```

### Supported Arguments & Flags

| Flag / Option | Type | Default | Description |
|---|---|---|---|
| `--date` | String (`YYYY-MM-DD`) | None | Explicit target date override. Takes precedence over `TARGET_DATE` env var. |
| `--dry-run` | Flag (`bool`) | `False` | Resolves target date, checks locks and idempotency without writing files or triggering pipeline. |
| `--verbose` | Flag (`bool`) | `False` | Emits `DEBUG` level log statements in addition to standard `INFO`/`ERROR`. |
| `--help` | Flag (`bool`) | N/A | Displays CLI usage syntax and argument descriptions. |

### Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `TARGET_DATE` | String (`YYYY-MM-DD`) | None | Fallback target date override if `--date` is omitted. |
| `DATABASE_URL` | String | `sqlite:///services/api/inventory.db` | Target PostgreSQL or SQLite connection string. |
| `RAW_DATA_DIR` | String | `data/raw` | Target directory for telemetry CSV exports. |

---

## 2. Exit Codes & Operating Semantics

| Exit Code | Classification | Meaning & Behavior |
|---|---|---|
| `0` | **Success / Clean Skip** | Job executed and completed successfully, OR skipped cleanly due to an active concurrency lock, OR skipped because the target date was already completed. |
| `1` | **Execution Failure** | Validation error (e.g. malformed date format), database connection error, CSV export failure, or non-zero exit from downstream pipeline subprocess. |

---

## 3. Log Stream Specification

Log messages are emitted to `sys.stdout` (for `INFO` and `DEBUG`) and `sys.stderr` (for `ERROR`) with standard timestamped formatting:

```text
YYYY-MM-DD HH:MM:SS,MS [LEVEL] [scripts.nightly_export] Message
```

### Standard Log Events

| Event | Level | Message Pattern |
|---|---|---|
| Initialization | `INFO` | `Nightly telemetry export initiated. Target date: YYYY-MM-DD` |
| Concurrency Lock Skip | `INFO` | `Active job 'nightly_export' currently processing (Run ID: ...). Skipping duplicate execution.` |
| Idempotency Skip | `INFO` | `Target date YYYY-MM-DD has already completed successfully (Run ID: ...). Skipping export.` |
| CSV Export Start | `INFO` | `Exporting telemetry events for YYYY-MM-DD to data/raw/telemetry_YYYY-MM-DD.csv` |
| CSV Pre-existing | `INFO` | `Audit file data/raw/telemetry_YYYY-MM-DD.csv already exists. Preserving existing snapshot.` |
| Pipeline Kickoff | `INFO` | `Spawning downstream KPI pipeline subprocess for target date YYYY-MM-DD` |
| Pipeline Success | `INFO` | `Downstream KPI pipeline completed successfully with exit code 0` |
| Job Completion | `INFO` | `Nightly telemetry export completed successfully for YYYY-MM-DD. Duration: 12.34s` |
| Execution Failure | `ERROR` | `Nightly export failed for YYYY-MM-DD: <sanitized error message>` |
