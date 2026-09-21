# Tasks: Containerization

**Input**: Design documents from [`/specs/012-containerization/`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization)

**Prerequisites**: [`plan.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/plan.md), [`spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/spec.md), [`research.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/research.md), [`data-model.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/data-model.md), [`contracts/`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/contracts)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Explicit file paths are included in all task descriptions.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Environment sample preparation and initial workspace configuration

- [x] T001 [P] Create sample environment file template in `.env.example`
- [x] T002 [P] Verify `.env` file exclusion in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Docker ignore manifests to prevent host artifact pollution during container builds

- [x] T003 [P] Create UI Docker ignore file excluding node_modules, .next, .env*, and *.log in `uis/.dockerignore`
- [x] T004 [P] Create Backend Docker ignore file excluding __pycache__, *.pyc, .env*, tests/, and *.log in `services/.dockerignore`

---

## Phase 3: User Story 1 - One-Command Local Platform Setup (Priority: P1) 🎯 MVP

**Goal**: Enable any team member to run `docker compose up` from repository root to launch Next.js website (port 3000), Next.js backoffice (port 3001), and FastAPI backend (port 8000) communicating via Docker network service names.

**Independent Test**: Execute `docker compose up --build` from repo root; verify website at `http://localhost:3000`, backoffice at `http://localhost:3001`, API docs at `http://localhost:8000/docs`, and inter-service container resolution.

### Implementation for User Story 1

- [x] T005 [P] [US1] Create UI start script launching website on port 3000 and backoffice on port 3001 in `uis/start.sh`
- [x] T006 [P] [US1] Create Node Alpine UI Dockerfile installing website and backoffice dependencies separately in `uis/Dockerfile`
- [x] T007 [P] [US1] Create Python Dockerfile installing `uv`, dependencies from requirements, and starting Uvicorn `--reload` in `services/Dockerfile`
- [x] T008 [US1] Create Docker Compose service orchestration and explicit bridge network in `docker-compose.yml`

**Checkpoint**: At this point, running `docker compose up` starts the entire platform without manual steps.

---

## Phase 4: User Story 2 - Hot-Reloading Development Workflow (Priority: P2)

**Goal**: Ensure source code changes on the host system instantly propagate to container processes without image rebuilds.

**Independent Test**: Edit a file in `/uis/website`, `/uis/backoffice`, or `/services/api` on the host and verify real-time hot reloading in the browser and Uvicorn log output.

### Implementation for User Story 2

- [x] T009 [US2] Add anonymous volume mounts for node_modules, .next, and __pycache__ in `docker-compose.yml`
- [x] T010 [US2] Verify host bind mounts and filesystem watch reloading across UI and Backend services in `docker-compose.yml`

**Checkpoint**: Code modifications reflect live in containers without rebuilding Docker images.

---

## Phase 5: User Story 3 - Environment Configuration & Secret Protection (Priority: P3)

**Goal**: Inject runtime configuration via root `.env` file and guarantee zero committed secrets in version control.

**Independent Test**: Search versioned Git files for hardcoded passwords/secrets and verify runtime containers load `.env` variables correctly.

### Implementation for User Story 3

- [x] T011 [P] [US3] Configure `env_file` loading for UI and Backend services in `docker-compose.yml`
- [x] T012 [US3] Perform secret hygiene scan verifying no credentials or keys exist in `docker-compose.yml` or Dockerfiles

**Checkpoint**: Environment management is secure, centralized, and excluded from version control.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification and documentation updates

- [x] T013 Execute end-to-end validation scenarios from [`specs/012-containerization/quickstart.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/quickstart.md)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Can start immediately in parallel with Setup.
- **User Story 1 (Phase 3)**: Depends on Phase 1 and Phase 2.
- **User Story 2 (Phase 4)**: Depends on User Story 1 completion.
- **User Story 3 (Phase 5)**: Depends on User Story 1 completion.
- **Polish (Phase 6)**: Depends on User Story 1, 2, and 3 completion.

### Parallel Opportunities

- **Phase 1**: `T001` and `T002` can run in parallel.
- **Phase 2**: `T003` and `T004` can run in parallel.
- **Phase 3**: `T005`, `T006`, and `T007` can run in parallel before `T008`.
- **Phase 5**: `T011` can run in parallel with US2 completion.
