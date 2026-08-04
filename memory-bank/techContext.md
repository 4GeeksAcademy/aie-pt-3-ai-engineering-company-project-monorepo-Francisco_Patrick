# Technical Context — TrackFlow

## Monorepo Structure

```text
/
├── package.json               # Root TypeScript configuration (trackflow-programming-foundations)
├── tsconfig.json              # TS compiler configuration (Target: ES2020, strict: true, outDir: dist)
├── CONTEXT.md                 # Official TrackFlow business context
├── copilot_instructions.md    # Frontend, accessibility, and Tailwind CSS development guidelines
├── company-choice.md          # Company selection rationale and technical vision
├── index.html                 # Main corporate landing page entry point
├── application.html           # Client application form interface
├── operations-playground.html # Manual testing playground for TypeScript utilities
├── src/                       # Core TypeScript business logic (Programming Foundations)
│   ├── types/                 # Entity type definitions and interfaces (entities.ts, query.ts)
│   └── utils/                 # Validation, filtering, aggregation, search, and sorting modules
├── packages/                  # Shared monorepo packages
│   └── shared/                # Shared types library (@repo/shared-types)
├── services/                  # Backend APIs, carrier connectors, and background workers
├── uis/                       # Frontend applications (Dashboards, Next.js, React, Streamlit, HTML)
├── data/                      # Data engineering hub
│   ├── raw/                   # Raw data (order emails, carrier API responses)
│   ├── process/               # Processed and cleaned datasets
│   ├── pipelines/             # Data transformation and ingestion pipelines
│   └── eval/                  # RAG and AI model evaluation datasets
├── infra/                     # Infrastructure as Code (Docker, Terraform, deployment configs)
├── internal/                  # Internal CLI tools and migration scripts
├── mcps/                      # Model Context Protocol (MCP) servers for AI tool integration
├── agents/                    # Agent patterns, templates, and prompt instructions
├── skills/                    # Reusable AI agent skills (executable instructions)
├── workflows/                 # Automation and workflow orchestration (n8n, Airflow/Composer)
├── memory-bank/               # Project memory bank (projectbrief.md, techContext.md, etc.)
├── docs/                      # Architecture documentation and guides
└── scripts/                   # Repository maintenance and automation scripts
```

---

## Tech Stack

### 1. Languages & Runtimes
- **TypeScript 5.9+:** Primary language for core business logic, domain validation, shared components, and backend services.
- **Node.js (ES2020):** Runtime environment for build processes, toolchains, and microservices execution.
- **HTML5 & CSS3 / Tailwind CSS:** Web standards for responsive, accessible, mobile-first corporate interfaces.
- **Python 3.11+ (Data/AI):** Used in data pipelines (`data/pipelines`), image processing, and AI model integrations.

### 2. Frontend & User Interface
- **Tailwind CSS:** Utility-first CSS framework (enforcing mobile-first design and consistent breakpoints: `sm:`, `md:`, `lg:`).
- **Semantic HTML & Accessibility (ARIA):** Full compliance with keyboard navigation, high color contrast, and Schema.org structured markup for SEO.
- **React / Next.js / Streamlit Dashboards:** Routed inside `uis/` for client portals, operational dashboards, and executive consoles.

### 3. Backend, APIs & Integrations
- **Node.js / TypeScript Microservices (`services/`):** REST/GraphQL API layer for warehouse abstraction, carrier aggregation, and returns processing.
- **Model Context Protocol (MCP Servers - `mcps/`):** Standardized protocol connecting Large Language Models (LLMs) to internal databases and external carrier APIs.

### 4. Artificial Intelligence, RAG & Agents
- **Multimodal LLMs (Claude / Gemini / OpenAI):** Natural language processing, visual product state classification from photos, and customer support response generation.
- **RAG Architecture (Retrieval-Augmented Generation):** Index-backed semantic knowledge base for bilingual (ES/EN) customer experience (CX) and operational support.
- **Agent Orchestration (`agents/` & `skills/`):** Autonomous agent workflows for stock validation, intelligent carrier selection, and sales risk analysis.

### 5. Automation & Infrastructure
- **n8n / Apache Airflow (`workflows/`):** Background workflow orchestration and automated email order parsing pipelines.
- **Docker & Docker Compose (`infra/`):** Containerization for microservices, MCP servers, and database instances.

---

## Architectural Decisions Made

1. **Unified Monorepo Architecture:**
   - Consolidated all codebases (frontend, backend, data pipelines, AI agents, and infrastructure) into a single monorepo to leverage shared strict types (`@repo/shared-types`) and guarantee cross-module consistency.

2. **Abstraction Layer Over Legacy Infrastructure:**
   - Built unified API facades in `services/` to decouple new applications from legacy systems (two distinct WMS implementations in Los Angeles and Zaragoza, plus a 2010-era ERP) without interrupting daily physical operations.

3. **Strict Typing & Defensive Domain Layer (`src/types` & `src/utils`):**
   - Enforced strict TypeScript rules (`noImplicitReturns`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) in domain utilities (`validation.ts`, `entities.ts`) to ensure malformed email or carrier payloads are rejected before database persistence.

4. **Adoption of Model Context Protocol (MCP):**
   - Prevented AI agents from querying production databases directly; all agent tool interactions route through secure, audited MCP servers defined in `mcps/`.

5. **Standard-Based, Accessible Frontend Design:**
   - Relied exclusively on Tailwind CSS and semantic HTML5 (ARIA, Schema.org) to deliver high-performance, lightweight, accessible web interfaces without bloated UI libraries.

6. **Departmental Feature Decomposition:**
   - Modularized project deliverables by business department (Warehouse Ops, Last-Mile, Reverse Logistics, CX, Sales, Telemetry, and Executive Direction) to support incremental milestone completion.

---

## Technical Constraints & System Debt

1. **Heterogeneous Warehouse Management Systems (WMS):**
   - The Los Angeles warehouse relies on commercial software, whereas Zaragoza uses advanced spreadsheets. The unified Inventory API must abstract both sources without forcing identical underlying database schemas.

2. **Integration Across 8 Disparate Carrier APIs:**
   - TrackFlow interfaces with 8 carriers (UPS, FedEx, DHL, MRW, SEUR, and local carriers) with differing rate limits, data formats (JSON/XML/SOAP), and availability SLAs.

3. **Cross-Border Dual Operations & Compliance:**
   - Active operations in two countries and time zones (US & Spain) require bilingual support (English/Spanish), multi-currency handling (USD/EUR), and strict GDPR compliance for European user data.

4. **Early-2010s Legacy ERP Technical Debt:**
   - Undocumented point-to-point Python scripts and cloud database fragmentation demand defensive API integrations and automated error handling.

5. **24/7 Continuous Operation Requirement:**
   - Public tracking portals and CX agents must operate 24/7 with aggressive caching and graceful fallback mechanisms during third-party API outages.
