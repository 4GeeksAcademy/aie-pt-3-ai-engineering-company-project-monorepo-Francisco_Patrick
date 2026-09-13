# Quickstart & Verification Guide: Authentication API Testing

**Feature**: `009-auth-api-tests`  
**Date**: 2026-09-13

## Prerequisites

1. **Python Environment**: Python >= 3.14 with `uv` package manager installed.
2. **Node.js Environment**: Node.js with `npm` or `npx jest` installed.

---

## Execution Steps

### 1. Execute FastAPI Backend Tests & Coverage

```bash
# Navigate to the services/api directory
cd services/api

# Run pytest suites cleanly
uv run pytest -v

# Run pytest with code coverage (Target >= 70%)
uv run pytest --cov=application/services --cov=infrastructure/adapters --cov=presentation/api --cov-report=term-missing
```

**Expected Outcome**:
- All test functions pass with `PASSED` status (0 failures, 0 errors).
- Overall line coverage for `auth_service.py`, `security_adapter.py`, `auth_routes.py`, and `user_routes.py` is at or above **70%**.

---

### 2. Execute TypeScript Frontend Auth Tests & Coverage

```bash
# Navigate to the backoffice UI directory
cd uis/backoffice

# Run Jest unit tests with coverage
npm test -- --coverage
# OR
npx jest --coverage
```

**Expected Outcome**:
- All tests in `__tests__/auth.test.ts` and `__tests__/authApi.test.ts` pass cleanly with 100% test success rate.

---

### 3. Verify `TESTING.md` Documentation

Check that [`TESTING.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/TESTING.md) at the project root contains:
- Commands for running pytest and Jest test suites.
- Full test case matrix (Happy Path, Edge Case, Failure Mode) for all 6 endpoints.
- Coverage result metrics (>= 70%).
- AI-assisted workflow and bug discovery notes.
