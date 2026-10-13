# Quickstart & Validation Guide: Containerization

**Feature**: Containerization (`012-containerization`)  
**Date**: 2026-09-21  

---

## 1. Prerequisites

- Docker Engine 24+ and Docker Compose V2 (`docker compose`) installed on host machine.
- Git repository cloned locally.

---

## 2. Launching Platform

Execute from repository root:

```bash
# 1. Copy sample environment file (if .env doesn't exist)
cp .env.example .env

# 2. Build and start containerized platform
docker compose up --build
```

---

## 3. End-to-End Validation Scenarios

### Scenario A: Service Accessibility
1. Open browser to `http://localhost:3000` -> Verify Next.js `website` home page loads.
2. Open browser to `http://localhost:3001` -> Verify Next.js `backoffice` home page loads.
3. Open browser to `http://localhost:8000/docs` -> Verify FastAPI Swagger interactive API documentation loads.

### Scenario B: Hot Reloading Verification
1. Edit a component title in `/uis/website/src/app/page.tsx` on host -> Verify instant reload on `http://localhost:3000`.
2. Edit a component title in `/uis/backoffice/src/app/page.tsx` on host -> Verify instant reload on `http://localhost:3001`.
3. Edit a route response in `/services/api/main.py` on host -> Verify Uvicorn detects change and reloads server without container restart.

### Scenario C: Inter-Service Networking Check
1. Execute inside UI container:
   ```bash
   docker exec -it trackflow-ui wget -qO- http://backend:8000/
   ```
2. Confirm 200 OK response from backend service.

### Scenario D: Secret Hygiene & Git Isolation Check
1. Verify `.env` file is excluded from Git tracking:
   ```bash
   git status --ignored | grep .env
   ```
2. Search repository tracked files for hardcoded secrets or passwords:
   ```bash
   git grep -i "secret" -- docker-compose.yml uis/Dockerfile services/Dockerfile
   ```
