# Network Resolution Contract: Inter-Service Communication

**Feature**: Containerization (`012-containerization`)  
**Date**: 2026-09-21  

---

## 1. Network Topology & Service DNS Rules

All containers participate in the user-defined bridge network `trackflow-net`.

```
                    +------------------------------------+
                    |             HOST NETWORK           |
                    |   http://localhost:3000 (Website)  |
                    |  http://localhost:3001 (Backoffice)|
                    |   http://localhost:8000 (Backend API)|
                    +------------------+-----------------+
                                       | Port Bindings
                                       v
+---------------------------------------------------------------------------------+
| DOCKER BRIDGE NETWORK: trackflow-net                                            |
|                                                                                 |
|   +--------------------------+               +------------------------------+   |
|   | Container: ui            |               | Container: backend           |   |
|   | Service Name: ui         |  SSR API Req  | Service Name: backend        |   |
|   |  - website (port 3000)   | ------------> |  - uvicorn main:app (8000)   |   |
|   |  - backoffice (port 3001)| http://backend:8000                          |   |
|   +--------------------------+               +------------------------------+   |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

## 2. Inter-Service Connection Rules

1. **Server-to-Server Communication (SSR / Internal API Calls)**:
   - Must use service name as host target: `http://backend:8000`
   - MUST NOT use `localhost`, `127.0.0.1`, or hardcoded IP addresses.

2. **Client-to-Server Communication (Browser Client Side)**:
   - Target host exposed port: `http://localhost:8000` (or `NEXT_PUBLIC_API_URL` environment variable).

3. **Validation Assertion**:
   - Code reviews and sign-off checks MUST verify that no container internal fetch or configuration defaults to `localhost` for container-to-container calls.
