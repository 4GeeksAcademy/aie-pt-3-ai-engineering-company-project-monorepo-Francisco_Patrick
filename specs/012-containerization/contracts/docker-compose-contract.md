# Interface Contract: Docker Compose Orchestration

**Feature**: Containerization (`012-containerization`)  
**Date**: 2026-09-21  

---

## 1. `docker-compose.yml` Specification

```yaml
version: '3.8'

services:
  ui:
    build:
      context: ./uis
      dockerfile: Dockerfile
    container_name: trackflow-ui
    ports:
      - "${WEBSITE_PORT:-3000}:3000"
      - "${BACKOFFICE_PORT:-3001}:3001"
    volumes:
      - ./uis:/app/uis
      - /app/uis/website/node_modules
      - /app/uis/website/.next
      - /app/uis/backoffice/node_modules
      - /app/uis/backoffice/.next
    env_file:
      - .env
    networks:
      - trackflow-net
    restart: unless-stopped

  backend:
    build:
      context: ./services
      dockerfile: Dockerfile
    container_name: trackflow-backend
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    volumes:
      - ./services:/app/services
    env_file:
      - .env
    networks:
      - trackflow-net
    restart: unless-stopped

networks:
  trackflow-net:
    name: trackflow-net
    driver: bridge
```

---

## 2. `.dockerignore` Specification

### `/uis/.dockerignore`
```text
node_modules
.next
.env*
*.log
.git
```

### `/services/.dockerignore`
```text
__pycache__
*.pyc
.env*
tests/
*.log
.venv
venv
.git
```
