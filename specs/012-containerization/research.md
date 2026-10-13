# Technical Research: Containerization

**Feature**: Containerization (`012-containerization`)  
**Date**: 2026-09-21  

---

## 1. Multi-App Next.js UI Container Architecture

### Decision
Use a single Alpine-based Node Dockerfile (`/uis/Dockerfile`) that installs dependencies for `/uis/website` and `/uis/backoffice` separately in build stages, and executes a `/uis/start.sh` entrypoint script to launch both Next.js applications concurrently (`website` on port 3000, `backoffice` on port 3001).

### Rationale
- Meets explicit user requirement for a single UI container running both applications.
- Separate `npm install` steps in `/uis/website` and `/uis/backoffice` prevent dependency leak or version conflicts between UI packages.
- Using background job execution with `wait -n` or `trap` in `start.sh` ensures both process signals and failures are handled cleanly.

### Alternatives Considered
- **Multiple Docker containers for UIs**: Rejected because requirement specifies a single UI container for both website and backoffice.
- **PM2 / Supervisord**: Adds extra heavy dependencies inside Alpine Node image. A clean POSIX shell script (`start.sh`) with background processes handles logging and process lifecycle natively.

---

## 2. Fast Python Package Installation with `uv`

### Decision
In `/services/Dockerfile`, install `uv` (Astral's fast Python package installer) and run `uv pip install --system -r api/requirements.txt` (or copy requirements file into build layer) to install FastAPI, Uvicorn, and dependencies directly into container Python environment.

### Rationale
- `uv` is significantly faster than standard `pip` for container image builds.
- `--system` flag ensures packages are installed in system Python site-packages without requiring separate virtual environment management inside the container.
- Uvicorn server is launched with `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload` to satisfy the live reloading requirement.

### Alternatives Considered
- **Standard `pip install`**: Functional but noticeably slower build times compared to `uv`.
- **`poetry` or `pipenv`**: Introduces unnecessary overhead given existing `requirements.txt` dependency manifest.

---

## 3. Inter-Service Communication & DNS Resolution

### Decision
Connect both UI and backend services using an explicitly defined Docker Compose custom bridge network (e.g. `trackflow-net`). Services communicate using Docker service names (e.g. `http://backend:8000` or `http://services:8000`).

### Rationale
- Custom bridge networks provide automatic container name resolution via Docker internal DNS.
- Client-side code running in host browsers accesses endpoints via host ports (`http://localhost:8000`), whereas server-side operations (Next.js server component API fetches / SSR) use internal Docker DNS (`http://backend:8000`).

### Alternatives Considered
- **Default bridge network**: Lacks automatic container DNS resolution by service name.
- **`host` networking**: Incompatible across cross-platform environments (Windows / macOS Docker Desktop).

---

## 4. Bind Mounts & Hot Reloading Strategy

### Decision
Configure volume bind mounts in `docker-compose.yml`:
- Host `./uis` mapped to `/app/uis` with anonymous volumes for `/app/uis/website/node_modules`, `/app/uis/website/.next`, `/app/uis/backoffice/node_modules`, and `/app/uis/backoffice/.next`.
- Host `./services` mapped to `/app/services` with anonymous volumes for `/app/services/api/__pycache__`.

### Rationale
- Prevents host platform build artifacts from clobbering container Linux binaries.
- Guarantees immediate source file change propagation from host editor to container watch filesystem event loop.
