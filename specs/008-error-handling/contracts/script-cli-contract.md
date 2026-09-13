# CLI Script Error Handling Contract

**Feature**: [`spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/spec.md)

## Standard Exit Codes

All Python CLI scripts (`scripts/analyze.py`, `scripts/seed_incidents.py`, `services/api/seed.py`) MUST adhere to standard POSIX process exit codes.

| Exit Code | Condition | Output Channel | Format / Message Example |
| :---: | :--- | :--- | :--- |
| `0` | Successful execution | `stdout` | Normal script output / summary report |
| `1` | General error (file missing, I/O error, corrupt input) | `stderr` | `Error: File 'invalid.csv' not found.` |
| `130` | Script terminated by user interrupt (Ctrl+C / SIGINT) | `stderr` | `\n[CANCELLED] Operation aborted by user.` |

---

## Output Stream Separation Rules

1. **`stdout`**: Reserved strictly for normal execution results, CSV export output, and summary reports.
2. **`stderr`**: Reserved strictly for warning messages (`[WARNING]`), error diagnostics (`[ERROR]`), and cancellation notices (`[CANCELLED]`).

---

## Defensive Pre-Execution Validation Contract

Before commencing stream processing or database modifications, scripts MUST perform pre-execution validation checks:

1. **File Existence Check**: Verify input file paths via `os.path.exists()` before opening streams.
2. **Read Permission Check**: Verify file readability before stream ingestion.
3. **Output Path Integrity**: Wrap output file creation in `try/except IOError` to catch write permission or path failures cleanly.
