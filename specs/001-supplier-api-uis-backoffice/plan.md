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

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A       | N/A        | N/A                                 |
