# Bug Assessment: Missing Project Delegation in Quickstart UV Commands Causing Missing Dependencies and Pytest Execution Failure

- **Slug**: 024-quickstart-uv-dependencies
- **Created**: 2026-11-10T11:38:00+01:00
- **Source**: Pasted text
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim or summarized)

The user reported the following terminal errors when attempting to execute the Quickstart Validation Guide for Feature `024-sales-forecasting-regression` from the monorepo root:

```text
# Quickstart testing
## Terminal Error
error: Failed to spawn: `pytest`
  Caused by: program not found
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> uv --version
uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> uv run python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"      
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import pandas, sklearn, scipy, matplotlib; print('All dependencies available')
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'pandas'
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> uv run python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports
Environment / Dependency error: Failed to import pipeline modules: No module named 'numpy'
```

## Symptom

When following [specs/024-sales-forecasting-regression/quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/quickstart.md) from the monorepo root, executing `uv run pytest ...`, `uv run python -c ...`, and `uv run python scripts/train_sales_forecast.py ...` fails:
1. `uv run pytest tests/pipelines/test_sales_forecast.py -v` fails immediately with `error: Failed to spawn: pytest Caused by: program not found`.
2. `uv run python -c "import pandas, ..."` fails with `ModuleNotFoundError: No module named 'pandas'`.
3. `uv run python scripts/train_sales_forecast.py ...` exits with status code 3 and stderr message `Environment / Dependency error: Failed to import pipeline modules: No module named 'numpy'`.

Expected behavior: All commands in `quickstart.md` should execute within the configured virtual environment containing project dependencies (`pandas`, `numpy`, `scikit-learn`, `scipy`, `matplotlib`, `pytest`), successfully discovering packages and running tests/training.

## Reproduction

1. Open PowerShell or terminal at the repository root: `J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo`.
2. Run `uv run pytest tests/pipelines/test_sales_forecast.py -v`. Observe error: `error: Failed to spawn: pytest Caused by: program not found`.
3. Run `uv run python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"`. Observe: `ModuleNotFoundError: No module named 'pandas'`.
4. Run `uv run python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports`. Observe process exit code 3: `Environment / Dependency error: Failed to import pipeline modules: No module named 'numpy'`.

## Suspected Code Paths

- [specs/024-sales-forecasting-regression/quickstart.md:27, 38, 55](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/quickstart.md#L27): Documents running `uv run python ...` and `uv run pytest ...` without specifying `--project services/api` or navigating into the project directory, assuming `uv` will implicitly locate the virtual environment from the monorepo root.
- [specs/024-sales-forecasting-regression/contracts/cli-contract.md:15-17](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/contracts/cli-contract.md#L15-L17): Mentions `uv run python scripts/train_sales_forecast.py [OPTIONS]` without specifying the project flag `--project services/api` required for monorepo root execution.
- [scripts/train_sales_forecast.py:22-50](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/scripts/train_sales_forecast.py#L22-L50): Implements the safe import try/except block that catches `ImportError` on `numpy` / pipeline dependencies and terminates with exit code 3 when running outside the virtual environment.
- [package.json:9-12](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/package.json#L9-L12): Defines monorepo test scripts utilizing `uv run --project services/api pytest ...`, but lacks dedicated convenience scripts for sales forecasting testing and training (e.g., `test:sales-forecast`, `train:sales-forecast`).
- [services/api/pyproject.toml:10-28](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/pyproject.toml#L10-L28): Declares `pytest`, `pandas`, `scikit-learn`, `scipy`, and `matplotlib` inside `services/api`, while the monorepo root has no root-level `pyproject.toml` workspace manifest.

## Root Cause Hypothesis

In this monorepo architecture, Python dependencies and the virtual environment (`.venv`) are housed inside `services/api/` (`services/api/pyproject.toml`). When `uv run` is invoked from the monorepo root without `--project services/api` (or without active `.venv`), `uv` searches the current working directory for a project manifest. Finding none at root, it falls back to isolated execution with system Python, where `pytest` is not installed on PATH and scientific dependencies (`pandas`, `numpy`, `scikit-learn`, `scipy`, `matplotlib`) are not resolved. 

When `--project services/api` is provided (e.g. `uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v`), all 13 pipeline tests pass and the pipeline executes with exit code 0.

Confidence: High.

## Proposed Remediation

**Preferred**: 
1. Update [specs/024-sales-forecasting-regression/quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/quickstart.md) to explicitly pass `--project services/api` across all commands (Environment Verification, Automated Test Verification, and Pipeline Execution) when executing from monorepo root, aligning with the monorepo conventions defined in [TESTING.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/TESTING.md) and [scripts/test_runner.ps1](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/scripts/test_runner.ps1).
2. Update [specs/024-sales-forecasting-regression/contracts/cli-contract.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/024-sales-forecasting-regression/contracts/cli-contract.md) to document the canonical monorepo execution syntax: `uv run --project services/api python scripts/train_sales_forecast.py [OPTIONS]`.
3. Add convenience npm scripts in [package.json](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/package.json) (e.g., `"test:sales-forecast": "uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v"` and `"train:sales-forecast": "uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports"`) to simplify root verification.

**Alternatives**:
- Configure a root `pyproject.toml` with `[tool.uv.workspace]` pointing to `services/api`. While feasible, this changes monorepo configuration semantics across existing tooling and CI/CD pipelines, whereas project delegation (`--project services/api`) is already the established pattern in `package.json` and `TESTING.md`.

**Files likely to change**:
- `specs/024-sales-forecasting-regression/quickstart.md`
- `specs/024-sales-forecasting-regression/contracts/cli-contract.md`
- `package.json`

**Tests to add or update**:
- Execute `uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v` to ensure 13/13 tests pass.
- Execute `uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports` to verify complete execution and artifact generation.

## Risks & Considerations

- Low risk: The proposed remediation changes documentation, command invocations, and developer convenience scripts without modifying production Python code or domain logic.
- Backward compatibility: Scripts executed directly inside `services/api/` continue working unchanged.

## Open Questions

- None. The monorepo patterns and reproduction evidence are unambiguous.

