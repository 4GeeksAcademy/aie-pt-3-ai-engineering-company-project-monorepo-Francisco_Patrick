# Bug Fix: Missing Project Delegation in Quickstart UV Commands

- **Slug**: 024-quickstart-uv-dependencies
- **Fixed**: 2026-11-10T11:43:40+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Updated `quickstart.md` and `cli-contract.md` to specify `--project services/api` for all root-level `uv run` commands, aligning with the monorepo architecture where Python dependencies and the virtual environment live under `services/api`. Added convenience npm scripts (`test:sales-forecast` and `train:sales-forecast`) to `package.json` for one-command execution from root.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `specs/024-sales-forecasting-regression/quickstart.md` | modified | Added `--project services/api` to environment check, pytest, and train script commands; documented npm shortcuts. |
| `specs/024-sales-forecasting-regression/contracts/cli-contract.md` | modified | Documented canonical monorepo root execution syntax with `--project services/api` and npm script invocation. |
| `package.json` | modified | Added `"test:sales-forecast"` and `"train:sales-forecast"` npm scripts pointing to `--project services/api`. |

## Diff Highlights (optional)

```diff
# specs/024-sales-forecasting-regression/quickstart.md
- uv run python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"
+ uv run --project services/api python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"

- uv run pytest tests/pipelines/test_sales_forecast.py -v
+ uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v
+ npm run test:sales-forecast

- uv run python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports
+ uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports
+ npm run train:sales-forecast
```

```diff
# package.json
+ "test:sales-forecast": "uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v",
+ "train:sales-forecast": "uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports"
```

## Tests Added or Updated

- `tests/pipelines/test_sales_forecast.py` — existing suite of 13 regression tests was executed and verified under `--project services/api` environment delegation.

## Local Verification

- Commands run:
  - `uv run --project services/api pytest tests/pipelines/test_sales_forecast.py -v` → 13/13 passed in 3.71s
  - `uv run --project services/api python -c "import pandas, sklearn, scipy, matplotlib; print('All dependencies available')"` → Output: `All dependencies available` (exit 0)
  - `uv run --project services/api python scripts/train_sales_forecast.py --data-path data/raw/trackflow_sales.csv --output-dir reports` → Success (exit 0), generated artifacts in `reports/` and `docs/`
  - `npm run test:sales-forecast` → 13/13 passed in 3.54s (exit 0)
  - `npm run train:sales-forecast` → Execution successful (exit 0)
- Manual checks:
  - Verified generated reports (`reports/sales_forecast_test_eval.png`, `reports/sales_forecast_evaluation.json`, `docs/training-model-decission.md`) remain valid and intact.

## Deviations from Assessment

None. All proposed remediation steps were applied as specified in `assessment.md`.

## Follow-ups

- Run `/speckit-bug-test slug=024-quickstart-uv-dependencies` to validate and formalize verification.

