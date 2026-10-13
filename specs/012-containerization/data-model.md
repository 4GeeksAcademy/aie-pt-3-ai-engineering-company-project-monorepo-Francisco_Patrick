# Infrastructure & Environment Data Model: Containerization

**Feature**: Containerization (`012-containerization`)  
**Date**: 2026-09-21  

---

## 1. Container Infrastructure Entities

### UI Service Entity (`ui`)
- **Base Image**: `node:20-alpine`
- **Workdir**: `/app/uis`
- **Exposed Ports**:
  - `3000`: `website` (Next.js App)
  - `3001`: `backoffice` (Next.js App)
- **Lifecycle Script**: `start.sh` (executes `npm run dev -- -p 3000` in website directory & `npm run dev -- -p 3001` in backoffice directory)
- **Mount Points**:
  - Host `./uis` -> Container `/app/uis`
  - Anonymous volume -> `/app/uis/website/node_modules`
  - Anonymous volume -> `/app/uis/website/.next`
  - Anonymous volume -> `/app/uis/backoffice/node_modules`
  - Anonymous volume -> `/app/uis/backoffice/.next`

### Backend Service Entity (`backend`)
- **Base Image**: `python:3.11-slim` (or `python:3.12-slim`)
- **Workdir**: `/app/services`
- **Exposed Ports**:
  - `8000`: FastAPI API Server (Uvicorn)
- **Lifecycle Command**: `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`
- **Mount Points**:
  - Host `./services` -> Container `/app/services`
  - Anonymous volume -> `/app/services/api/__pycache__`

### Network Entity (`trackflow-net`)
- **Type**: Custom Docker Bridge Network
- **DNS Resolution**: Automatic container service name resolution (`ui`, `backend`)

---

## 2. Environment Variables & Secret Schema

All variables are defined in repository root `.env` (git-ignored) with fallbacks documented in `.env.example`.

| Variable | Target Service | Purpose | Default / Example Value |
| :--- | :--- | :--- | :--- |
| `NODE_ENV` | `ui` | Runtime environment mode | `development` |
| `WEBSITE_PORT` | `ui` | Host port for website app | `3000` |
| `BACKOFFICE_PORT` | `ui` | Host port for backoffice app | `3001` |
| `BACKEND_PORT` | `backend` | Host port for backend FastAPI | `8000` |
| `INTERNAL_BACKEND_URL` | `ui` (SSR) | Server-side container-to-container URL | `http://backend:8000` |
| `NEXT_PUBLIC_API_URL` | `ui` (Browser) | Client-side browser API URL | `http://localhost:8000` |
| `SECRET_KEY` | `backend` | JWT / Security Secret Key | `dev-secret-key-change-in-prod` |
