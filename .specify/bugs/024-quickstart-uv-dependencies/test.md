# Bug Verification: Missing Project Delegation in Quickstart UV Commands

- **Slug**: 024-quickstart-uv-dependencies
- **Tested**: 2026-11-10T11:46:30+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug is fully resolved. Running root-level `uv` commands with `--project services/api` or via the newly defined `npm run` shortcuts executes successfully inside the target Python virtual environment, resolving all scientific and test dependencies (`pandas`, `numpy`, `scikit-learn`, `scipy`, `matplotlib`, `pytest`). All 13 sales forecasting regression tests and the full pipeline training execution passed with zero errors or regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `uv run --project services/api python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"` | pass | Cleanly imported all dependencies; printed `All dependencies available`. |
| New / updated tests | `uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v` | pass | 13/13 sales forecast tests passed in 3.50s. |
| Pipeline Execution (documented) | `uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports` | pass | Executed end-to-end, generated metrics JSON, PNG visual report, and decision documentation. |
| Convenience scripts | `npm run test:sales-forecast` & `npm run train:sales-forecast` | pass | Both npm shortcuts executed successfully with exit code 0. |
| Regression suite | `npm run test:jobs` | pass | 16/16 existing background export runner tests passed in 2.47s. |
| Lint / type-check | `npm run typecheck` | pass | TypeScript compile check (`tsc --noEmit`) passed with zero errors. |

## Output Excerpts

### Dependency Check Output
```text
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> uv run --project services/api python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"
All dependencies available
```

### Pytest Verification Output
```text
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo
configfile: pytest.ini
plugins: anyio-4.14.2, cov-7.1.0
collecting ... collected 13 items

tests/pipelines/test_sales_forecast.py::test_sales_data_ingestion_and_schema PASSED [  7%]
...
tests/pipelines/test_sales_forecast.py::test_cli_exit_code_validation_error PASSED [100%]

============================= 13 passed in 3.50s ==============================
```

### Training Pipeline Execution Output
```text
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports
======================================================================
 TRACKFLOW SALES FORECASTING ENGINE — EXECUTIVE SUMMARY
======================================================================
Dataset: data\raw\trackflow_sales.csv (120 consolidated monthly records)
Temporal Split:
  - Training Period : 2016-01-01 to 2023-12-01 (96 months)
  - Test Period     : 2024-01-01 to 2025-12-01 (24 months)
  - Chronological Integrity: VERIFIED (Zero Leakage)
...
Artifacts Generated:
  - Visual Forecast Chart     : reports/sales_forecast_test_eval.png
  - Metric Summary JSON       : reports/sales_forecast_evaluation.json
  - Decision Document         : docs/training-model-decission.md
======================================================================
```

## Residual Risks

- Developers executing `uv run` from the monorepo root without referencing the quickstart instructions or npm scripts might still omit `--project services/api`. The updated `quickstart.md` and `cli-contract.md` clearly document this requirement.

## Recommendation

Close the bug — verified end-to-end. All quickstart instructions work as expected from the monorepo root and convenience scripts function properly.

