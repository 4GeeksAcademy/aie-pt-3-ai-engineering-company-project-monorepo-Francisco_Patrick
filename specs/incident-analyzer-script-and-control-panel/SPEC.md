# SPEC.md: Internal Incident Analysis Pipeline & Interface
## 1. Overview & Goal
Build an internal, secure incident analysis platform for After-Sales Support to process customer incident records (complaints, requests, operational failures) containing sensitive PII without relying on external AI services.

The project is structured in two sequential phases:
1. **Phase 1 (CLI Prototype):** Validate schema constraints and metric calculations against a 100-record test CSV using a standalone Python script, designed to scale up to 1M rows.
2. **Phase 2 (Platform Integration):** Integrate the validated engine into backend API services and a web backoffice for CSV uploads, metric visualization, and report exports.

## 2. Monorepo Structure
The repository must follow this specific directory layout:

```text
.
├── scripts/
│   ├── analyze.py              # Analysis & validation script (Phase 1)
│   └── incidents-COMPANY.csv   # 100-row test dataset (see CONTEXT)
├── services/
│   └── api/                    # Backend service (analysis & export endpoints)
└── uis/
    └── backoffice/             # Web interface (file upload & data visualization)

```

---

## 3. Data Integrity & Validation Rules

### Data Privacy & Performance

* **Internal Execution:** All processing runs strictly on local/internal infrastructure; zero PII transmission to external LLMs/APIs.
* **Scale Target:** Scalable design capable of streaming/chunking up to 1,000,000 records.

### Validation Criteria

A record is classified as **Invalid** (corrupt/incomplete) if:

* Any required field (defined in `CONTEXT`) is missing or empty.
* Any categorical field contains an unrecognized value outside the allowed enum set (e.g., disallowed `status` or `category`).

### Handling Strategy

* **Strict Exclusion:** Invalid records must be excluded from primary aggregations.
* **Auditability:** Count, catalog, and report invalid records with rejection reasons—never drop rows silently.

## 4. Phased Implementation

### Phase 1: Standalone Script (`scripts/analyze.py`)

* **Input:** `scripts/incidents-COMPANY.csv`.
* **Execution:**
1. Stream and parse CSV records.
2. Validate each record against schema and allowed enum sets.
3. Track invalid row counts and error classifications.
4. Compute aggregated metrics (volume, status distribution, category breakdown, resolution metrics).


* **Output:** Terminal summary verifying calculations match the expected baseline figures from `CONTEXT`.

### Phase 2: Platform Integration (`services/api/` & `uis/backoffice/`)

* **Backend (`services/api`):**
* `POST /api/incidents/upload` — Ingests CSV file, executes validation/aggregation engine, returns metrics + invalid row diagnostics.
* `GET /api/incidents/export` — Generates and downloads the summary report as a CSV file.

* **Frontend (`uis/backoffice`):**
* File upload zone for browser-based CSV ingestion.
* Summary dashboard displaying computed metrics and data health indicators (valid vs. corrupt count).
* Direct "Export CSV" trigger to download reports without terminal access.

## 5. Acceptance Criteria

* [ ] **Phase 1 Validation:** `scripts/analyze.py` executes against `scripts/incidents-COMPANY.csv` and matches all expected `CONTEXT` totals.
* [ ] **Error Accounting:** Invalid/corrupt records are explicitly tracked and logged without aborting execution.
* [ ] **Monorepo Compliance:** All code and assets reside in their assigned directories (`scripts/`, `services/api/`, `uis/backoffice/`).
* [ ] **End-to-End Workflow:** Non-technical staff can upload CSVs via `uis/backoffice`, review aggregations, and export summary CSVs via `services/api`.