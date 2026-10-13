# Implementation Plan: Containerization

**Branch**: `012-containerization` | **Date**: 2026-09-21 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/spec.md)

**Input**: Feature specification from [`/specs/012-containerization/spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/012-containerization/spec.md)

---

## Summary

Containerize `/uis` (website on port 3000, backoffice on port 3001 in a single UI container) and `/services` (FastAPI with `uv` and Uvicorn `--reload`), orchestrated using Docker Compose with bind mounts for hot reloading and an explicit bridge network for inter-service DNS resolution (`http://backend:8000`).

---

## Technical Context

**Language/Version**: Node 20 Alpine (UI container), Python 3.11/3.12 (Backend container)  
**Primary Dependencies**: Next.js 14, React 18, FastAPI, Uvicorn, `uv`, Docker, Docker Compose V2  
**Storage**: Local files / SQLite (`inventory.db`, `db.json` inside backend service)  
**Testing**: Container spin-up validation, inter-service HTTP connectivity, hot reloading smoke tests  
**Target Platform**: Linux containers running on Docker Desktop / Docker Engine (Windows/macOS/Linux)  
**Project Type**: Monorepo containerization & local orchestration  
**Performance Goals**: Container startup under 30s; host code edit to container hot reload under 3s  
**Constraints**: Zero committed secrets/passwords; `.env` ignored by Git; `.dockerignore` files present; service-to-service calls use Docker service names instead of `localhost`  
**Scale/Scope**: 2 container services (`ui` running 2 Next.js apps, `backend` running FastAPI API)  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Service Isolation**: UI container and Backend container maintain distinct dependencies and working directories.
- [x] **Environment Variable Injection**: All variables loaded exclusively from root `.env`.
- [x] **No Hardcoded Secrets**: Zero API keys or secrets in `docker-compose.yml` or `Dockerfile`s.
- [x] **Reproducible Developer Workflow**: Single `docker compose up` command launches entire stack.

---

## Project Structure

### Documentation (this feature)

```text
specs/012-containerization/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 technical research
├── data-model.md        # Phase 1 infrastructure & data model
├── quickstart.md        # Phase 1 validation guide
├── contracts/           # Phase 1 contract specifications
│   ├── docker-compose-contract.md
│   └── inter-service-networking.md
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code Layout

```text
/
├── docker-compose.yml              # Monorepo container orchestration
├── .env.example                    # Sample environment variables template
├── .gitignore                      # Git ignore file (verifies .env present)
│
├── uis/                            # UI Applications directory
│   ├── Dockerfile                  # Node Alpine image for website + backoffice
│   ├── start.sh                    # Startup script launching ports 3000 & 3001
│   ├── .dockerignore               # Ignores node_modules, .next, .env*, *.log
│   ├── website/                    # Next.js website (port 3000)
│   └── backoffice/                 # Next.js backoffice (port 3001)
│
└── services/                       # Backend FastAPI service directory
    ├── Dockerfile                  # Python image with uv & Uvicorn --reload
    ├── .dockerignore               # Ignores __pycache__, *.pyc, .env*, tests/, *.log
    └── api/                        # FastAPI main application & endpoints
```

**Structure Decision**: Monorepo orchestration structure with dedicated Dockerfiles in `/uis` and `/services`, and a root `docker-compose.yml`.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No constitution violations present.*
