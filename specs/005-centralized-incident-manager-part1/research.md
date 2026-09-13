# Technical Research: Centralized Incident Manager - Part I

## 1. Storage & Persistence Architecture

- **Decision**: Utilize TinyDB via `services/api/infrastructure/database.py` with an `incidents` table/collection.
- **Rationale**: Monorepo standard established in `services/api` for lightweight local database persistence without requiring external database servers during evaluation.
- **Alternatives Considered**:
  - SQLite: Rejected to maintain consistency with existing `TinyDBUserRepository` and `TinyDBProfileRepository` patterns in `services/api`.
  - In-memory dict: Rejected because seed data must persist across API process restarts.

## 2. Shared Code Extraction & Monorepo Organization

- **Decision**: Extract/place shared validation and transformation engine functions in `shared/analyzer/engine.py` (or `packages/shared/incidents/`).
- **Rationale**: `scripts/seed_incidents.py`, `scripts/analyze.py`, and `services/api` all need access to identical CSV validation and transformation rules.
- **Alternatives Considered**:
  - Duplicate validation logic in seed script: Rejected because requirement explicitly mandates reusing existing validation logic across CLI scripts and API services.

## 3. Historical CSV Transformation & Idempotency Strategy

- **Decision**: Store the original CSV record ID as `legacy_id` in the database entity when seeding. Before inserting a record, query TinyDB for `legacy_id == csv_row.id` (or `origin == 'customer' AND legacy_id == csv_row.id`).
- **Rationale**: Guaranteed idempotency when running `python scripts/seed_incidents.py` repeatedly.
- **Transformation Mapping**:
  - `id` (CSV) -> `legacy_id` (Model); new system `id` generated automatically (e.g. `inc_<uuid>` or `inc_<seq>`).
  - `description` (CSV) -> `title` (Model)
  - `details` / `description` -> `description` (Model)
  - `category` (CSV) -> `category` (Model, validated against allowed set)
  - `status` (CSV): `open` -> `open`, `closed` -> `resolved`, `discarded` -> `discarded`
  - `date` (CSV) -> `created_at` & `updated_at` (Model ISO-8601 string)
  - `location` (CSV) -> `branch` (Model, defaulting to `central` if empty/unspecified)
  - `origin` -> Fixed to `"customer"` for historical CSV seeds.

## 4. Friendly Error Handling & Exception Middleware

- **Decision**: Implement custom FastAPI exception handler and domain error classes returning clean JSON responses (`{"error": "<user-friendly message>", "details": ...}`) with HTTP 400/422/500 codes.
- **Rationale**: Requirement explicitly dictates "error messages that users understand, not stack traces".

## 5. Summary Aggregation Endpoint

- **Decision**: Expose `GET /api/incidents/summary` in `services/api`.
- **Rationale**: Returns counts by `status` and `category` matching transformed historical values after seeding.
