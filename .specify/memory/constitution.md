<!--
# Sync Impact Report
- Version Change: Template (Unratified) → 1.0.0
- Modified Principles:
  - Template Slot 1 (PRINCIPLE_1_NAME) → I. Service Boundaries & Domain Isolation
  - Template Slot 2 (PRINCIPLE_2_NAME) → II. Public API Compatibility & Strict Contract Serialization
  - Template Slot 3 (PRINCIPLE_3_NAME) → III. Strict TypeScript & Static Type Safety
  - Template Slot 4 (PRINCIPLE_4_NAME) → IV. Defensive Error Handling & Zero Sensitive Data Leaks
  - Template Slot 5 (PRINCIPLE_5_NAME) → V. Performance-First Architecture & Core Web Vitals Standards
- Added Principles:
  - VI. Test-First Development & Deterministic Verification Gates
- Added Sections:
  - Architecture & Service Boundary Constraints (replaces SECTION_2_NAME)
  - Development Workflow & Quality Gates (replaces SECTION_3_NAME)
- Removed Sections:
  - None (All template placeholder sections concretized)
- Follow-up Deferred Items:
  - None
-->

# TrackFlow Monorepo Constitution

## Core Principles

### I. Service Boundaries & Domain Isolation (NON-NEGOTIABLE)
Monorepo architectural boundaries MUST be strictly preserved across all subprojects.
- Frontend user interfaces reside exclusively within `uis/` (`uis/backoffice`, `uis/website`, `uis/talent-pipeline-tracker`) and MUST NEVER directly access local backend database files (`db.json`, `inventory.db`) or import backend Python modules.
- Backend services reside in `services/api/` and MUST maintain clean hexagonal/layered boundaries: domain models and business rules (`domain/`), application orchestration (`application/services/`), database and third-party adapters (`infrastructure/`), and API controllers (`presentation/` and `routes/`).
- Cross-cutting types and shared contracts MUST be published to `packages/shared/` (`@repo/shared-types`). Frontends and internal utilities MUST consume shared domain models through this package rather than duplicating type definitions.
- Utility scripts in `scripts/` and operational migration tools in `internal/` MUST remain isolated and interact with domain data solely through designated service APIs or standalone CLI interfaces.
- Inter-service communication MUST occur via formalized HTTP REST endpoints. Cross-boundary file imports or cyclic dependencies between top-level directories are strictly forbidden.

### II. Public API Compatibility & Strict Contract Serialization (NON-NEGOTIABLE)
All public REST API endpoints MUST maintain backward compatibility and adhere to deterministic serialization contracts.
- 100% of FastAPI endpoints in `services/api/` MUST declare explicit Pydantic `response_model` specifications, typed request bodies, and status codes.
- Data Transfer Object (DTO) Projections: Internal domain models, ORM/storage primitives, and sensitive fields (`hashed_password`, secret reset tokens) MUST NEVER be leaked across HTTP boundaries. Endpoints MUST project output data through dedicated response schemas (e.g., `UserResponse`, `MessageResponse`, `IncidentAnalysisResponse`).
- Breaking changes to public route paths, request payloads, query parameters, or response structures are prohibited without an explicit deprecation cycle, migration path, and a MAJOR semantic version increment.
- Public API contract changes MUST be verified against consuming frontend clients before deployment.

### III. Strict TypeScript & Static Type Safety
All TypeScript code in `uis/` and `packages/` MUST strictly comply with workspace type constraints.
- Code MUST strictly satisfy `tsconfig.json` compiler flags: `strict: true`, `noImplicitReturns`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.
- Zero `any` policy: The `any` type annotation is strictly banned. Engineers MUST use explicit interfaces, type aliases, or generics.
- Unsafe type assertions (e.g. `as unknown as Type`) and compiler suppression comments (`@ts-ignore`, `@ts-expect-error`, `@ts-nocheck`) MUST NOT be used.
- All exported functions, methods, and classes MUST define explicit return type annotations and complete JSDoc documentation detailing parameters, expected ranges, and error states.
- Type imports MUST be explicitly annotated using `import type { ... }` syntax.
- Python backend modules MUST maintain corresponding type hygiene using type annotations and Pydantic validation models across all domain boundaries.

### IV. Defensive Error Handling & Zero Sensitive Data Leaks
Robust error handling and secure logging practices MUST be enforced across every layer of the system.
- Zero Raw Error Exposure: Handlers MUST NOT expose internal stack traces or raw runtime exception messages (`str(e)`) to clients inside HTTP 500 responses. All exceptions MUST be logged internally with tracebacks, returning sanitized, user-safe error messages to consumers.
- Zero PII & Credential Leakage: Plaintext authentication tokens, password reset links, and Personally Identifiable Information (PII, including customer email addresses) MUST NEVER be logged to standard output, console streams, or persistent audit records. Logs MUST mask PII and store only cryptographic hashes of tokens.
- No Swallowed Failures: Generic catch-all blocks that silently suppress errors (`except: pass`, empty `catch` blocks) are strictly forbidden. All external network requests, database operations, and file I/O MUST have explicit error handling, custom domain exceptions, or non-zero exit codes in CLI scripts (`sys.exit(1)`).
- Resilient UI Error States: Frontend views MUST handle asynchronous network and API failures with user-visible error notifications and actionable retry mechanisms (CTAs), avoiding infinite loading spinners or corrupted UI state.

### V. Performance-First Architecture & Core Web Vitals Standards
Web applications MUST deliver state-of-the-art user experience backed by strict Core Web Vitals thresholds.
- Production Target Metrics: Frontend applications (`uis/backoffice`, `uis/website`) in production builds (`next build && next start`) MUST maintain:
  - Largest Contentful Paint (LCP) ≤ 1.0s
  - Total Blocking Time (TBT) ≤ 200ms
  - Cumulative Layout Shift (CLS) = 0
- Baseline Modern JavaScript: Applications MUST target modern JavaScript baseline (`target: ES2022`) to prevent unnecessary polyfill overhead and helper bloat.
- Hydration Gatekeeper Prohibition: Client authentication and hydration guards MUST NOT block the initial Server-Side Rendered (SSR) DOM or delay LCP element painting with full-screen loading spinners.
- Long Task Elimination: Monolithic client bundles and below-the-fold component trees MUST leverage dynamic code splitting (`next/dynamic`) and deferred evaluation to ensure main-thread execution tasks remain below 50ms.
- Performance audits MUST be benchmarked against production builds to eliminate development server (`next dev`) Hot Module Replacement (HMR) overhead.

### VI. Test-First Development & Deterministic Verification Gates
Reliability and stability MUST be guaranteed through automated verification pipelines.
- Test-First Culture: Critical business logic, pricing engines, carrier scoring algorithms, and inventory validations SHOULD follow test-driven practices with automated unit and integration coverage.
- Deterministic Seeding: Database and script seed routines (`scripts/seed_incidents.py`, `services/api/seed.py`) MUST be idempotent, deterministic, and protected by per-record error handling against malformed CSV or database payloads.
- Automated Quality Gates: No feature may be merged without passing all static analysis gates:
  - TypeScript type checking (`npm run typecheck`) with zero compiler errors.
  - Production build compilation (`npm run build`).
  - Backend test execution (`pytest`).
  - Zero regressions against public API serialization and error handling audit baselines.

## Architecture & Service Boundary Constraints

### Directory Responsibilities
The monorepo structure reflects clear organizational separation:
- `uis/`: Contains end-user web applications (e.g. Next.js App Router frontends). Responsible for presentation, client-side routing, and user interaction. Strictly consumes backend functionality via HTTP REST APIs.
- `services/`: Contains backend microservices and APIs (e.g. `services/api/` FastAPI service). Responsible for core business logic, domain entities, transaction integrity, and persistence abstractions.
- `packages/shared/`: Centralized TypeScript package (`@repo/shared-types`). Publishes shared DTOs, domain interfaces, and utility validators.
- `scripts/`: Operational tools, data analysis scripts, and database seed runners. MUST parse parameters cleanly and report errors via standard error streams and exit codes.
- `internal/`: Internal utilities, packaged migration scripts, and administrative CLIs.
- `infra/`: Containerization (`Dockerfile`, `docker-compose.yml`), deployment configurations, and infrastructure-as-code manifests.
- `data/`: Raw data samples, pipeline inputs, and evaluation datasets.

### Database & Persistence Isolation
- Persistence layers (TinyDB, SQLite, or future relational/document stores) are encapsulated within `services/api/infrastructure/adapters/`.
- Direct file modifications to database files (`db.json`, `inventory.db`) from outside service persistence adapters are strictly prohibited.
- Application services and presentation routes MUST access data through abstract repository ports, ensuring backend engines can swap storage implementations without breaking callers.

## Development Workflow & Quality Gates

### Pull Request & Pre-Merge Verification
Every proposed change MUST pass the following verification sequence prior to integration:
1. **Static Analysis & Type Integrity**: Execute workspace type check (`npm run typecheck` across all TypeScript packages). Zero `any` types, zero compiler warnings.
2. **Backend Integrity**: Execute backend test suite (`pytest`) within `services/api/`. Validate route status codes and Pydantic response models.
3. **Build Validation**: Verify production build success (`npm run build`). Ensure zero unhandled build warnings or missing dependencies.
4. **Serialization & Security Audit**: Validate that all new or updated API endpoints declare explicit `response_model` decorators, expose zero password hashes or PII, and return sanitized errors.
5. **Performance & Core Web Vitals**: Ensure new UI routes conform to Core Web Vitals targets (LCP ≤ 1.0s, TBT ≤ 200ms) under production builds.

## Governance

### Authority & Supersedence
This Constitution represents the authoritative engineering policy for the TrackFlow monorepo. Its principles and constraints supersede informal practices, personal preferences, and unrecorded development conventions.

### Amendment Procedure
1. Any proposed modification or principle addition must be submitted as an architectural RFC / specification documenting the problem, alternatives considered, and concrete impact analysis across monorepo service boundaries.
2. Breaking changes to existing principles, service boundaries, or public contracts require review and formal approval by TrackFlow Tech leadership (CTO Andrés Kim, Engineering Leads).
3. Approved amendments MUST update this document, increment the version according to semantic versioning rules, record the amendment date, and document rationale in the Sync Impact Report.

### Semantic Versioning Policy
- **MAJOR (X.0.0)**: Incompatible architectural shifts, principle deletions, or fundamental restructuring of service boundaries or governance rules.
- **MINOR (1.X.0)**: Addition of new principles, structural sections, or material expansion of development constraints that maintain backward compatibility with existing principles.
- **PATCH (1.0.X)**: Wording refinements, typographical corrections, non-semantic clarifications, or reference updates.

### Compliance Review
All pull requests, architecture specs, and automated agents operating in this repository MUST verify active compliance against this Constitution. Any intentional deviation must be documented with an explicit justification and temporary exception grant.

---

**Version**: 1.0.0 | **Ratified**: 2026-10-12 | **Last Amended**: 2026-10-12
