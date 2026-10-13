# Implementation Plan: supplier-api-uis-backoffice

**Branch**: `001-supplier-api-uis-backoffice` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-supplier-api-uis-backoffice/spec.md`

## Summary

Implement a FastAPI backend with TinyDB for managing suppliers/carriers, and a Next.js/React backoffice UI to view, filter, create, and update suppliers.

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.9+
**Primary Dependencies**: FastAPI, Pydantic, TinyDB, Next.js, Tailwind CSS
**Storage**: TinyDB (JSON file based)
**Testing**: pytest, jest
**Target Platform**: Node.js & Python environments
**Project Type**: Web Service (API) & Web App (UI)
**Performance Goals**: API response <200ms
**Constraints**: JSON Storage, Tailwind CSS, Semantic HTML

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Use of TinyDB and standard API principles.
- Use of Tailwind CSS for UI.

## Project Structure

### Documentation (this feature)

```text
specs/001-supplier-api-uis-backoffice/
├── plan.md              # This file
├── research.md          
├── data-model.md        
├── quickstart.md        
└── tasks.md             
```

### Source Code (repository root)

```text
services/
  api/
    main.py
    models.py
    database.py
    routes/
      suppliers.py
    seed.py

uis/
  backoffice/
    app/
      suppliers/
        page.tsx
        layout.tsx
    components/
      SupplierTable.tsx
      SupplierForm.tsx
```

**Structure Decision**: Placed backend in `services/api` as per previous context and frontend in `uis/backoffice` using Next.js App Router structure.

## Integration & Refactoring Strategy

### Backend (API Service)
The `services/api/main.py` file already exists and serves the Incident Analyzer endpoints. To prevent losing or breaking the existing source:
- **Do not overwrite `main.py`**: We will refactor `main.py` to use `fastapi.APIRouter`. 
- **Modular Routes**: The new Supplier API endpoints will be encapsulated in a router within `services/api/routes/suppliers.py`.
- **Integration**: In `main.py`, we will simply import and `app.include_router(suppliers_router, prefix="/suppliers")` without modifying the existing `/api/incidents/analyze` routes.
- **Data persistence**: TinyDB initialization will be handled carefully in `services/api/database.py` without interfering with the existing in-memory state of the incident analyzer.

### Frontend (Backoffice UI)
The backoffice application (`uis/backoffice`) is an existing Next.js application.
- **Layout Preservation**: We will integrate a new navigation link to the Supplier Directory within the existing UI layout or navigation menu.
- **Modular Components**: The new UI code will be contained in `app/suppliers/page.tsx` and isolated components (`components/SupplierTable.tsx`, `components/SupplierForm.tsx`).
- **No Overwriting**: We will not overwrite existing global state, CSS styles (other than extending Tailwind classes), or the existing incident logic components.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A       | N/A        | N/A                                 |
