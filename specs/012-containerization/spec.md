# Feature Specification: Containerization

**Feature Branch**: `012-containerization`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "Feature: Containerization - Reproducible development environment with Docker Compose for UI applications (website & backoffice) and Backend FastAPI services."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-Command Local Platform Setup (Priority: P1)

As a software engineer onboarding or working on the project, I want to start the full application platform (frontend UIs and backend API) using a single command, so that I can immediately develop without manual setup or dependency resolution issues.

**Why this priority**: Solves developer onboarding friction, eliminates environment inconsistencies, and provides a reproducible environment for the entire team.

**Independent Test**: Can be fully verified by running `docker compose up` from the root directory on a fresh clone and confirming that all services start without manual intervention and respond on expected host ports.

**Acceptance Scenarios**:

1. **Given** a cloned repository with Docker installed, **When** a developer executes `docker compose up` from the repository root, **Then** both UI applications (`website` on port 3000, `backoffice` on port 3001) and the backend API server start successfully and are reachable from the host machine.
2. **Given** running containerized services, **When** services communicate with each other over the network, **Then** inter-service calls use dedicated Docker network service names rather than `localhost` or hardcoded IP addresses.

---

### User Story 2 - Hot-Reloading Development Workflow (Priority: P2)

As a frontend or backend developer, I want my host code changes to instantly reflect in the running containerized applications without rebuilding Docker images, so that my development flow remains fast and interactive.

**Why this priority**: High developer productivity requires rapid iteration loops without waiting for image rebuilds.

**Independent Test**: Can be tested by modifying a source file in `/uis` or `/services` on the host system and verifying that hot-reloading automatically triggers and updates the running application in real time.

**Acceptance Scenarios**:

1. **Given** running UI containers, **When** a developer edits frontend code in `/uis/website` or `/uis/backoffice` on the host, **Then** Next.js development server automatically reloads and displays updated UI in the browser.
2. **Given** running backend containers, **When** a developer edits Python code in `/services` on the host, **Then** Uvicorn reloads the API server process automatically with updated endpoints.

---

### User Story 3 - Environment Configuration & Secret Protection (Priority: P3)

As a security-conscious engineer, I want all sensitive credentials and configuration variables to be managed via `.env` files that are ignored by version control, so that secrets are never exposed in Dockerfiles or orchestration configurations.

**Why this priority**: Prevents credential leaks in git history and ensures compliant secret management across environments.

**Independent Test**: Can be tested by running security checks verifying no secrets/credentials exist in `Dockerfile` or `docker-compose.yml`, and verifying `.env` is ignored in `.gitignore`.

**Acceptance Scenarios**:

1. **Given** configuration settings in a root `.env` file, **When** Docker Compose launches services, **Then** environment variables are injected into containers without hardcoding values in version-controlled files.
2. **Given** a local repository workspace, **When** reviewing git status or performing commits, **Then** `.env` is ignored by Git and never committed to repository history.

---

### Edge Cases

- What happens when ports 3000, 3001, or 8000 are already in use on the host system? System should fail with a clear port binding error or allow host port override via `.env`.
- How does the system handle missing `.env` file on initial startup? System should provide clear error guidance or rely on standard sample environment defaults.
- How does file permissions/ownership behave when mounted source code creates build artifacts or cache directories on the host? Ignore files via `.dockerignore` to avoid host dirty working tree issues.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a root-level orchestration setup using Docker Compose to launch all platform services with a single command.
- **FR-002**: System MUST containerize the UI layer (`/uis`), running both the `website` application (port 3000) and `backoffice` application (port 3001) simultaneously from a single UI container via an automated startup script.
- **FR-003**: System MUST isolate UI dependencies, installing Node dependencies for `/uis/website` and `/uis/backoffice` separately during container image build based on Node Alpine.
- **FR-004**: System MUST containerize the Python FastAPI backend (`/services`), installing dependencies using `uv` and launching Uvicorn with auto-reload enabled.
- **FR-005**: System MUST configure source code bind mounts for both UI and backend services to enable real-time hot reloading on code modification.
- **FR-006**: System MUST create an explicitly named Docker network connecting UI and backend services, requiring all internal service-to-service communication to use Docker service names instead of `localhost`.
- **FR-007**: System MUST inject environment variables into all containers using a root `.env` file, strictly preventing any hardcoded secrets or API keys in Dockerfiles or `docker-compose.yml`.
- **FR-008**: System MUST maintain `.dockerignore` files in `/uis/` and `/services/` excluding build outputs (`.next`, `node_modules`), caches (`__pycache__`, `*.pyc`), environment files (`.env*`), and log files (`*.log`).
- **FR-009**: System MUST ensure `.env` file is listed in `.gitignore` and excluded from repository commits.

### Key Entities

- **UI Service Container**: Container encapsulating both Next.js applications (`website` and `backoffice`), exposed on host ports 3000 and 3001.
- **Backend Service Container**: Container encapsulating FastAPI service running Uvicorn server with `uv` package manager and auto-reload.
- **Platform Network**: Dedicated Docker bridge network enabling service resolution by container service name.
- **Environment Configuration**: Centralized key-value environment pairs defined in `.env` for service runtime configuration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% automated environment spin-up with zero manual configuration steps beyond executing `docker compose up`.
- **SC-002**: Development onboard time for new team members reduced from hours of dependency setup to under 5 minutes.
- **SC-003**: Source code edits on host system reflect in browser/API within 3 seconds without image rebuilds.
- **SC-004**: Zero committed secrets or credentials in git repository history across all Docker configuration files.
- **SC-005**: 100% of inter-service network requests resolve successfully using Docker service names.

## Assumptions

- Target developers have Docker Engine and Docker Compose V2 installed on their local operating systems (Windows/macOS/Linux).
- Existing source code directories `/uis/website`, `/uis/backoffice`, and `/services` contain valid package/dependency manifests (`package.json`, `requirements.txt`).
- Standard ports 3000, 3001, and backend API ports are available for binding on host interfaces.
