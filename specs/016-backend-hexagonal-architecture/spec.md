# Feature Specification: Backend Architecture - Switch to Hexagonal

**Feature Branch**: `016-backend-hexagonal-architecture`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "/speckit-specify # Backend Architecture: Switch to Hexagonal\n## Overview\nThe task is to analyze the actual state of the backend architecture and files organization in `services/api`, creating a `docs/backend-state-analysis.md` with API endpoints gruped by domain, contracts, use case in the actual state. The document must clarify the best way to adopt a Hexagonal Architecture for the backend. Proposing the changes needed, the files migration and reestructuration.\n### What To Do\n* Analyze the current backend architecture and file organization inside the `services/api` directory.\n* Create a new documentation file at `docs/backend-state-analysis.md`.\n* Group and document all existing API endpoints by domain, contracts, and their current use cases.\n* Formulate a proposal outlining the best approach for adopting a Hexagonal Architecture (Ports and Adapters) for the backend.\n* Detail the necessary structural changes, file migrations, and code restructuring plan required to transition to the Hexagonal Architecture.\n### Acceptance Criteria\n* The `docs/backend-state-analysis.md` file is successfully created in the correct path.\n* The document includes a comprehensive inventory of all current API endpoints grouped logically by domain, contract definitions, and actual use cases.\n* The transition plan clearly explains how Hexagonal Architecture will be mapped and adopted for the backend.\n* A concrete migration roadmap and file restructuring proposal (detailing directory layouts, layer separation, and file movements) are explicitly provided."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Comprehensive Backend State & Endpoint Inventory (Priority: P1)

As an engineering lead and backend developer, I need an exhaustive inventory and architectural evaluation of all existing API endpoints, data models, and persistence dependencies in `services/api` categorized by domain and contract, so that our team has complete, objective visibility into the current backend state before executing structural refactoring.

**Why this priority**: Without a complete baseline of current endpoints, data contracts, and layer couplings, any architectural restructuring risks introducing regression bugs, breaking frontend client contracts, or leaving orphaned code paths.

**Independent Test**: Review `docs/backend-state-analysis.md` and verify that every active endpoint across all domains (Suppliers, Inventory, Telemetry, Authentication, User Management, User Profiles, Incidents, and Incident Stream Analysis) is cataloged with HTTP method, URI path, file location, input/output contracts, and business use cases.

**Acceptance Scenarios**:

1. **Given** the active backend service in `services/api`, **When** the state analysis is inspected, **Then** all active endpoints across disparate router locations (`routes/`, `routers/`, `presentation/api/`, and `main.py`) are indexed with their HTTP method, route path, request payload schema, response model, auth requirement, and business use case.
2. **Given** the cataloged endpoints, **When** evaluating architectural boundaries, **Then** current anti-patterns (such as route handlers directly executing database queries, SQLModel session injection into controllers, missing repository abstractions, and hardcoded adapter types) are explicitly documented.
3. **Given** public API contracts consumed by frontends (`uis/backoffice`, `uis/website`), **When** reviewing the inventory, **Then** contract serialization adherence and DTO projections are validated against TrackFlow Constitution standards.

---

### User Story 2 - Hexagonal Architecture Target Model & Domain Boundary Proposal (Priority: P1)

As a software architect, I need a concrete target design that maps TrackFlow's backend domains to Hexagonal Architecture (Ports and Adapters) principles, so that business logic remains completely isolated from HTTP frameworks, database engines, and third-party integrations.

**Why this priority**: Defines the canonical design pattern for all backend development. Clear boundaries prevent layer leaking and ensure heterogeneous storage backends (TinyDB document store and SQLite/PostgreSQL relational database) can be swapped or tested without modifying business logic.

**Independent Test**: Verify that the proposal defines distinct Domain (Entities & Business Rules), Application (Use Cases & Orchestration), Driving Ports & Adapters (FastAPI Routers / HTTP handlers), and Driven Ports & Adapters (Repository Ports, Database Adapters, Cache, Security, and Email).

**Acceptance Scenarios**:

1. **Given** TrackFlow core domains (Suppliers, Inventory, Incidents, Auth/Users, Telemetry), **When** reviewing the architectural proposal, **Then** each domain has a defined boundary containing pure domain models, application use cases, and technology-agnostic port interfaces.
2. **Given** external infrastructure dependencies (TinyDB, SQLModel/PostgreSQL, JWT cryptography, in-memory caching), **When** reviewing adapter specifications, **Then** all infrastructure components implement driven port interfaces rather than being directly coupled to application services or route handlers.
3. **Given** application services, **When** examining dependency directions, **Then** all dependencies flow inward toward the domain core, with dependency injection configured centrally in presentation dependencies or startup composition roots.

---

### User Story 3 - Incremental Migration Roadmap & File Restructuring Plan (Priority: P2)

As a release engineer and backend maintainer, I need a phased migration roadmap and an explicit file restructuring matrix (detailing current path, target path, and refactoring action for every module), so that the transition can be executed in verifiable, low-risk increments with zero service downtime or breaking API changes.

**Why this priority**: Monolithic migrations carry high risk of regressions. An incremental, phased plan allows our team to migrate domain by domain while maintaining automated test passes and continuous integration stability at every step.

**Independent Test**: Review the restructuring plan and verify that every existing file in `services/api` is accounted for in a before/after mapping table, and each migration phase specifies clear prerequisites, actions, and verification gates.

**Acceptance Scenarios**:

1. **Given** current directory sprawl (`routes/`, `routers/`, `presentation/api/`, root `models.py`, root `schemas.py`), **When** consulting the restructuring matrix, **Then** a unified, clean directory structure is specified with exact target paths for every module.
2. **Given** existing automated test suites (`tests/api/`, `tests/unit/`), **When** stepping through the phased roadmap, **Then** each phase defines verification gates (unit tests, integration tests, type checks) that must pass before advancing to the next phase.
3. **Given** active frontend applications, **When** implementing the migration, **Then** all public API paths and response formats remain 100% backward compatible throughout the entire transition.

---

### Edge Cases

- **Dual Storage Engine Coexistence**: The backend simultaneously uses TinyDB (JSON document store) and SQLModel/SQLAlchemy (SQLite/PostgreSQL relational database). The hexagonal design must support both engines via distinct adapter implementations without leaking ORM models into domain services.
- **In-Memory Streaming & Global State**: Incident CSV stream analysis currently maintains state in global variables in `main.py` (`last_analysis_result`). The migration must encapsulate this state within an application service or cache adapter without breaking CSV streaming downloads.
- **Dynamic Imports in Controllers**: Route handlers in `auth_routes.py` dynamically instantiate adapters and repositories inside endpoint functions. The proposal must outline moving these to composition roots or FastAPI dependency injection providers.
- **Mixed Caching Strategies**: Endpoint-level caching using `response_cache` is embedded directly into route handlers with manual cache invalidation. The target architecture must provide a clean strategy for caching at adapter boundaries.
- **Route Path Prefix Divergence**: Current routes have inconsistent prefixes (`/suppliers`, `/inventory/...`, `/api/incidents/...`, `/telemetry/events`). The restructuring must preserve existing URLs for backward compatibility while establishing consistent canonical routing patterns.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate a comprehensive backend architectural state analysis and hexagonal transition document at `docs/backend-state-analysis.md`.
- **FR-002**: The document MUST provide an exhaustive catalog of all existing API endpoints across `services/api`, categorized into logical business domains: Suppliers, Inventory, Telemetry, Authentication, User Management, User Profiles, Incidents, and Incident Stream Analysis.
- **FR-003**: For every cataloged endpoint, the document MUST record: HTTP method, full URI path, source file location, request payload schema, response model schema, HTTP status codes, authentication/authorization requirements, and current use case description.
- **FR-004**: The document MUST analyze and document all current architectural anti-patterns, layer boundary violations, and tight couplings present in `services/api` (including direct DB access in controllers, ORM sessions in services, missing ports, and ad-hoc routes in `main.py`).
- **FR-005**: The document MUST formulate a complete Hexagonal Architecture (Ports and Adapters) target model for `services/api/`, establishing strict layer separation: Domain (Entities, Value Objects, Domain Exceptions), Application (Use Cases, Services), Driving Adapters (API Routers, Controllers), and Driven Adapters (Persistence, Security, Cache, Email).
- **FR-006**: The document MUST specify abstract port definitions (interfaces) for all persistence repositories and external infrastructure services across all domains.
- **FR-007**: The document MUST provide an explicit file-by-file restructuring matrix detailing current path, proposed target path, architectural layer classification, and required refactoring actions for every file currently in `services/api/`.
- **FR-008**: The document MUST outline a phased, non-breaking migration roadmap detailing execution order, dependencies between phases, backward compatibility safeguards, and test verification criteria for each phase.
- **FR-009**: The architectural proposal MUST strictly adhere to TrackFlow Monorepo Constitution principles, enforcing Domain Isolation (Principle I), Public API Compatibility & Strict Contract Serialization (Principle II), Defensive Error Handling (Principle IV), and Test-First Verification Gates (Principle VI).

### Key Entities

- **API Endpoint Descriptor**: Encapsulates route metadata including HTTP verb, URI path, domain group, input/output schema contracts, security dependencies, and business purpose.
- **Domain Module**: A self-contained business bounded context (e.g., Inventory, Incidents, Auth, Suppliers) containing domain logic independent of external technology.
- **Port Interface**: An abstract contract defining interactions between the application layer and external systems (Driven Port, e.g., repository or notification port) or between clients and application services (Driving Port).
- **Adapter**: A concrete implementation of a port interfacing with specific infrastructure (e.g., `TinyDBIncidentRepository`, `SQLModelInventoryRepository`, `FastAPIRouter`).
- **File Migration Mapping**: A structured record defining the transition of a specific source file to its target hexagonal destination, including layer assignment and necessary refactoring tasks.
- **Migration Phase**: A discrete, sequential milestone in the transition roadmap with defined prerequisites, execution steps, and verification gates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of active backend API endpoints across all routers, routes, presentation modules, and `main.py` are documented with complete contract specifications and use cases in `docs/backend-state-analysis.md`.
- **SC-002**: 100% of existing architectural anti-patterns and layer boundary violations across `services/api` are identified and cataloged with specific remediation recommendations.
- **SC-003**: The Hexagonal Architecture proposal defines concrete port interfaces and layer assignments for all 8 backend functional domains.
- **SC-004**: The file restructuring matrix accounts for 100% of files in `services/api/` with zero orphaned modules or ambiguous target paths.
- **SC-005**: The migration roadmap provides an end-to-end transition path guaranteeing 100% backward compatibility for all existing HTTP client contracts and passing 100% of backend automated tests at every milestone.

## Assumptions

- **FastAPI Framework Retention**: The backend service will continue using FastAPI as its primary HTTP framework; hexagonal architecture will decouple business logic from FastAPI primitives rather than replacing the framework.
- **Dual Database Architecture Preservation**: The coexistence of TinyDB (JSON document store) and SQLModel/PostgreSQL (relational inventory engine) remains an intentional architectural choice that will be accommodated through separate repository adapters.
- **Public URL Stability**: All existing public HTTP route paths and response payload shapes will remain backward compatible to prevent breaking changes in Next.js frontends (`uis/backoffice`, `uis/website`).
- **No Immediate Schema Migration**: The architecture analysis and restructuring plan focuses on code organization, layer decoupling, and port abstractions without requiring breaking changes to database schemas or existing persistent data files (`db.json`, `inventory.db`).
- **Documentation Deliverable**: The primary deliverable for this specification is the creation of `docs/backend-state-analysis.md` as an authoritative architectural reference and transition guide.
