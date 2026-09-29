# Implementation Plan: Caching & Lazy Loading Optimization

**Branch**: `014-caching-optimization` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-caching-optimization/spec.md`

## Summary

Implement frontend dynamic lazy loading (`next/dynamic`) and memoization (`useMemo`) across `uis/website` and `uis/backoffice`, implement in-memory TTL caching with write-through invalidation for high-cost stable endpoints (`/api/incidents/summary`, `/suppliers`, `/inventory/products`) in `services/api/`, and compile a comprehensive `CACHING_REPORT.md` documenting architectural decisions, tradeoffs, and exclusions.

## Technical Context

**Language/Version**: Python 3.14 (FastAPI backend), TypeScript 5.x / Next.js 14+ / React 18+ (Frontend)

**Primary Dependencies**: FastAPI, Pydantic, SQLModel, TinyDB, Next.js (`next/dynamic`), React (`useMemo`, `lazy`, `Suspense`)

**Storage**: In-memory thread-safe dictionary with TTL expiration for server-side response cache; SQLite & TinyDB for underlying storage.

**Testing**: `pytest` for backend cache unit & endpoint invalidation tests; Jest / React Testing Library for frontend components.

**Target Platform**: Node.js & modern web browsers (client); Windows / Linux server (backend).

**Project Type**: Monorepo Web Application & RESTful API Service.

**Performance Goals**: Sub-millisecond response times for cached read endpoints on cache hits; deferred client bundle chunks for non-critical views.

**Constraints**: Zero sensitive/session data stored in shared cache keys; 100% immediate invalidation on mutating writes.

**Scale/Scope**: 31 backend endpoints audited; 3 high-impact read endpoints cached; 2+ frontend components lazy loaded; 1+ non-trivial `useMemo` optimization.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Zero Implicit Any Rule**: Strict TypeScript types enforced across all new frontend components and helper functions.
- **Explicit Return Types & JSDoc**: All exported functions/methods documented with return types and JSDoc annotations.
- **Security & Privacy**: No sensitive user/session fields in shared cache keys.
- **Status**: PASSED.

## Project Structure

### Documentation (this feature)

```text
specs/014-caching-optimization/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-contracts.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
services/api/
├── infrastructure/
│   └── cache.py                       # In-memory TTL cache utility with prefix invalidation
├── presentation/api/
│   └── incident_routes.py             # Incident summary endpoint with caching & mutation invalidation
├── routes/
│   └── suppliers.py                   # Suppliers list endpoint with caching & mutation invalidation
├── main.py                            # Inventory products endpoint with caching & mutation invalidation
└── tests/
    ├── unit/
    │   └── test_cache.py              # Unit tests for ResponseCache (TTL, hit/miss, invalidation)
    └── api/
        └── test_cached_endpoints.py   # Integration tests for endpoint caching & invalidation

uis/backoffice/
├── app/
│   ├── inventory/
│   │   ├── orders/page.tsx            # Lazy-loaded OrdersHistoryTable
│   │   └── products/page.tsx          # Lazy-loaded ProductTable
│   └── incidents/page.tsx             # Lazy-loaded IncidentSummaryPanel & IncidentListPanel
├── components/
│   └── inventory/
│       └── OrdersHistoryTable.tsx     # useMemo composite volume metrics calculation

CACHING_REPORT.md                      # Comprehensive technical decisions and tradeoffs report
```

**Structure Decision**: Monorepo structure enhancing existing services and UI packages without introducing unnecessary dependencies.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | Standard in-memory TTL cache and React dynamic imports are lean, zero-overhead patterns. | External Redis cluster would introduce unnecessary infrastructure complexity for the current monorepo scale. |
