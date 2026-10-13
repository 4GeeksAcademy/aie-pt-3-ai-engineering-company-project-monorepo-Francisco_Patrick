# TrackFlow - Backend Architecture Proposal

## 1. Architectural Pattern Selection and Justification

**Selected Pattern:** Hexagonal Architecture (Ports & Adapters) combined with Domain-Driven Design (DDD).

**Justification based on TrackFlow's Characteristics:**
- **Heterogeneous Systems (WMS):** TrackFlow operates with two disparate Warehouse Management Systems (WMS) — Los Angeles uses commercial software, while Zaragoza relies on advanced spreadsheets. Hexagonal architecture allows us to define a standard "Inventory Port" (interface) for the core domain and implement two separate, decoupled adapters (e.g., `LAWMSAdapter`, `ZaragozaSpreadsheetAdapter`). The core business logic remains entirely agnostic to the underlying storage or legacy systems.
- **Multiple External Integrations:** We must integrate with 8 disparate carrier APIs (JSON, XML, SOAP) with different rate limits and data structures. Each carrier can be encapsulated as an adapter implementing a unified "Carrier Port", isolating the core routing and tracking logic from vendor-specific volatility.
- **Cross-Border Complexity:** Domain logic involving multi-currency handling (USD/EUR) and cross-border routing rules must be strictly isolated from HTTP delivery mechanisms or external third-party APIs.
- **Maintainability & 24/7 SLAs:** Given the 24/7 continuous operation requirement for public tracking portals and CX agents, modifications to a single carrier API integration or WMS legacy script must not risk taking down the core system. Hexagonal architecture guarantees this isolation boundary.

---

## 2. Folder and Module Structure

The proposed structure blends standard FastAPI conventions with a domain-driven approach, clearly separating concerns according to Hexagonal principles:

```text
services/backend/
├── app/
│   ├── main.py                  # FastAPI application instance and core startup events
│   ├── core/                    # App-wide configurations, security, and global exceptions
│   │   ├── config.py            # Environment variables (Pydantic BaseSettings)
│   │   ├── security.py          # Authentication/Authorization logic
│   │   └── exceptions.py        # Global exception handlers
│   ├── api/                     # Delivery Mechanism (HTTP/REST - The "Driving Ports")
│   │   ├── dependencies.py      # FastAPI Depends() injections (DB sessions, Auth, etc.)
│   │   └── v1/                  # API versioning
│   │       ├── inventory.py
│   │       ├── carriers.py
│   │       ├── orders.py
│   │       └── returns.py
│   ├── domain/                  # Core Business Logic (Entities and Use Cases)
│   │   ├── inventory/
│   │   ├── orders/
│   │   └── returns/
│   ├── infrastructure/          # Adapters to external systems (The "Driven Adapters")
│   │   ├── database/            # Database configurations and ORM models (SQLAlchemy)
│   │   ├── wms/                 # Adapters for LA and Zaragoza WMS
│   │   └── carriers/            # Adapters for the 8 carrier APIs
│   └── tests/                   # Unit and integration tests
├── requirements.txt             # Project dependencies
└── Dockerfile                   # Container definition for deployment
```

**Separation Criteria:**
- **Core:** Global application configuration and security, entirely independent of specific features.
- **API (Driving Ports):** Handles HTTP requests, routes, and request/response payload validation using Pydantic. It acts as an entry point, delegating all heavy lifting to the domain layer.
- **Domain:** Pure business logic. Does not know about HTTP, FastAPI, or specific databases/carrier APIs.
- **Infrastructure (Driven Adapters):** Concrete implementations for external services (WMS, Carriers, Relational DBs).

---

## 3. FastAPI Endpoints and Routers Organization

Routes are explicitly grouped by business domains using FastAPI's `APIRouter`. Rather than placing all routes in a massive `main.py` file, each domain owns its specific router module under `app/api/v1/`.

- **Inventory Router (`app/api/v1/inventory.py`)**
  - `GET /inventory` - Retrieves aggregated stock across all warehouses.
  - `GET /inventory/{warehouse_id}/{sku}` - Retrieves specific stock levels.
  - `POST /inventory/sync` - Triggers synchronization with physical WMS (LA or Zaragoza).
- **Orders Router (`app/api/v1/orders.py`)**
  - `POST /orders/ingest` - Receives and parses new orders.
  - `GET /orders/{order_id}` - Retrieves detailed order information.
- **Carriers & Tracking Router (`app/api/v1/carriers.py`)**
  - `POST /carriers/select` - Intelligent selection of the optimal carrier for a shipment.
  - `GET /carriers/tracking/{tracking_number}` - Unified tracking endpoint aggregating the 8 carrier systems.
- **Returns Router (`app/api/v1/returns.py`)**
  - `POST /returns/request` - Initiates a smart return request.
  - `POST /returns/inspect` - Processes AI-assisted inspection photos for automated state classification.

These routers are connected in `app/main.py` using `app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])`.

---

## 4. FastAPI Standard Structure and Research

**Research Summary:**
FastAPI is highly unopinionated compared to frameworks like Django. However, the community heavily gravitates towards patterns advocated by its creator (Sebastián Ramírez) and popular cookiecutter templates (e.g., the official `Full Stack FastAPI Template`).
Typical community conventions include:
- Relying on a central `main.py` as the application entry point.
- Separating concerns into distinct modules like `api` (for routing), `core` (for config/security), `crud` (for database operations), and `schemas` (for Pydantic models).
- Heavy utilization of FastAPI's dependency injection (`Depends()`) for managing database sessions and authentication flows.
- Utilizing Pydantic's `BaseSettings` within a `core/config.py` file for robust environment variable management.

**Influence on our Decisions:**
Our proposal adopts these essential conventions (such as `main.py`, `core/config.py`, and the `api/v1/` router separation), but intentionally adapts the generic `crud` pattern into a Domain-Driven Hexagonal approach. Instead of a generic `crud` folder that groups all database operations together, we group by domain and infrastructure (e.g., `domain/inventory`, `infrastructure/wms`). This is a concrete decision made to handle TrackFlow's significant complexity (heterogeneous WMS and 8 carriers), which a simple CRUD architecture would struggle to maintain cleanly.

---

## 5. Frontend and Backend Coexistence

TrackFlow utilizes a unified monorepo approach for Next.js frontends (`uis/website`, `uis/backoffice`) and the backend API (`services/backend`). 

- **Monorepo Integration:** While the frontend and backend coexist in the same Git repository to leverage shared standards, they operate as fully separated, scalable processes.
- **API Communication & CORS:** The Next.js client applications communicate with the FastAPI backend over HTTP/REST. Because the frontend and backend run on different ports (and eventually different domains in production), the backend must explicitly configure Cross-Origin Resource Sharing (CORS). We will use FastAPI's `CORSMiddleware` in `main.py` to allow origins specifically mapping to our frontend deployments.
- **Environment Variables:** Both systems use distinct `.env` files. The frontend securely exposes non-sensitive routing keys (e.g., `NEXT_PUBLIC_API_URL` pointing to the backend). Conversely, the backend's `.env` securely holds sensitive credentials (WMS access keys, Carrier API secrets, Database passwords) which are parsed and validated at runtime by Pydantic's `BaseSettings`.

---

## 6. Risks and Points of Attention

- **Risk 1: Leaking Infrastructure Details into the Domain:** If developers bypass the repository/adapter pattern and write direct carrier API HTTP calls or SQL queries inside the API routers or domain services, the codebase will become tightly coupled. Modifying a carrier API integration would then require rewriting core API routes, directly threatening the 24/7 continuous operation SLA.
- **Risk 2: Shared State and Monolith Bottlenecks:** Although organized neatly in a monorepo structure, if the backend domains are not strictly separated, changes in the Returns engine might accidentally bleed over and break the Inventory sync. Without proper isolation boundaries, the system risks becoming a "big ball of mud" despite having a clean folder structure, making future deployments highly risky.
