# Quickstart Validation Guide: Backend Hexagonal Architecture

**Feature**: Backend Architecture - Switch to Hexagonal  
**Branch**: `016-backend-hexagonal-architecture`  
**Date**: 2026-10-13  
**Status**: Complete  

---

## Overview

This quickstart guide provides step-by-step instructions to validate the Hexagonal Architecture transition for `services/api`. It outlines environment prerequisites, test commands, and verification criteria demonstrating that all domains operate correctly through ports and adapters with 100% backward compatibility.

---

## 1. Prerequisites & Environment Setup

### Environment Requirements
* Python `>= 3.14` (installed and managed via `uv` or virtual environment)
* Working directory: `services/api`
* Environment configuration: `.env` file present (or `.env.example` copied to `.env`)

### Setup Command
```powershell
# From repository root
cd services/api
uv sync
```

---

## 2. Validation Scenarios

### Scenario 1: Verify Architectural Layer Boundary Isolation (Static Inspection)
**Goal**: Ensure zero imports of persistence engines (TinyDB, SQLModel) or transport frameworks (FastAPI) inside the `domain/` layer.

**Execution**:
```powershell
# Run grep / ripgrep check for prohibited framework imports in domain/
git grep -E "from (fastapi|sqlmodel|tinydb|sqlalchemy)" services/api/domain/
```

**Expected Outcome**: Zero matches. The domain layer must be 100% pure Python business logic and port interfaces.

---

### Scenario 2: Unit Testing with Mock Repository Ports
**Goal**: Verify that application services execute business rules deterministically using mock repository ports without reading or writing disk files (`db.json`, `inventory.db`).

**Execution**:
```powershell
uv run pytest tests/unit/ -v
```

**Expected Outcome**: 100% of unit tests pass, confirming domain logic and application services run in complete isolation from storage engines.

---

### Scenario 3: Backward-Compatible API Endpoint Contract Verification
**Goal**: Verify that all 23 active endpoints across all 8 functional domains respond with identical HTTP status codes and Pydantic schemas.

**Execution**:
```powershell
uv run pytest tests/api/ -v
```

**Expected Outcome**: All route tests pass across:
1. `tests/api/test_auth.py`
2. `tests/api/test_users.py`
3. `tests/api/test_profiles.py`
4. `tests/api/test_cached_endpoints.py`
5. `tests/api/test_telemetry.py`
6. `tests/test_inventory_products.py`
7. `tests/test_inventory_orders.py`
8. `tests/test_incident_status_lifecycle.py`

---

### Scenario 4: Dual Storage Engine Verification (TinyDB & SQLModel)
**Goal**: Verify that both persistence adapters function correctly through their respective repository ports:
- `TinyDBSupplierRepository` & `TinyDBIncidentRepository` reading/writing JSON documents
- `SQLModelInventoryRepository` managing SQLite relational transactions

**Execution**:
```powershell
uv run pytest tests/test_inventory_stock_guard.py tests/test_incident_validation.py -v
```

**Expected Outcome**: Stock guard invariants (preventing outbound exits exceeding available inventory) and incident status transition lifecycle rules execute cleanly.

---

### Scenario 5: Full Backend Verification Suite
**Goal**: Run the entire backend test suite and coverage reporting.

**Execution**:
```powershell
uv run pytest --cov=. --cov-report=term-missing
```

**Expected Outcome**: All tests pass with zero unhandled exceptions, zero sensitive data leaks in logs, and no regressions.

---

## 3. Related Artifacts
* [Feature Specification](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/016-backend-hexagonal-architecture/spec.md)
* [Architectural State Analysis](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docs/backend-state-analysis.md)
* [Phase 0 Research](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/016-backend-hexagonal-architecture/research.md)
* [Data Model](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/016-backend-hexagonal-architecture/data-model.md)
* [API Contracts](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/016-backend-hexagonal-architecture/contracts/)
