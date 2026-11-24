# Bug Assessment: RFP Intake Pipeline Relocation & React 18 Dynamic Route Fix

- **Slug**: rfp-pipeline-relocation-react18
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> la estructura no cumple: el BRIEFING pide el pipeline/grafo bajo data/pipelines/rfp_intake/ y está en services/api/application/agent/. Mueve los cinco módulos y el grafo a data/pipelines/rfp_intake/, deja el router importando/disparando y actualiza imports/tests. Además, el detalle uis/backoffice/app/rfp/[id]/page.tsx usa use(params) de React 19 con React 18; el build no lo soporta

## Symptom

1. **Monorepo Architecture Violation**: The RFP Intake & Agentic Analysis Pipeline and its multi-agent LangGraph workflow were implemented inside the FastAPI backend application layer (`services/api/application/agent/`) rather than under the shared data engineering domain at `data/pipelines/rfp_intake/` as mandated by `trackflow-BRIEFING.es.md` and feature architectural standards.
2. **Frontend Build Failure due to React 19 Hook on React 18**: `uis/backoffice/app/rfp/[id]/page.tsx` imports and calls `use(params)` from React 19 / Canary, while `@trackflow/backoffice` runs React 18.3.1 (`"react": "^18.3.1"` and `next@^14.2.5`). React 18 does not export `use()`, and Next.js 14 App Router client/server dynamic route pages expect synchronous `{ params: { id: string } }` (or client-side `useParams()` from `next/navigation`), breaking TypeScript typechecking and the production Next.js build.

## Reproduction

1. **Inspect Pipeline Files**:
   Run `ls services/api/application/agent/` to observe the five modules (`rfp_classifier_agent.py`, `rfp_orchestrator_agent.py`, `rfp_department_workers.py`, `rfp_synthesizer_agent.py`, `rfp_intake_pipeline.py`) located under the API service rather than `data/pipelines/rfp_intake/`.
2. **Inspect Backoffice Page**:
   Inspect `uis/backoffice/app/rfp/[id]/page.tsx:3,19,30`. Observe `import React, { ..., use } from 'react'` and `const resolvedParams = use(params);`.
3. **Trigger Frontend Build / Typecheck**:
   Run `npm run build` in `uis/backoffice`. The compiler fails with type errors and incompatibility on React 18/Next 14 page params.

## Suspected Code Paths

- `services/api/application/agent/rfp_classifier_agent.py` — Classifier agent currently located in backend application namespace.
- `services/api/application/agent/rfp_orchestrator_agent.py` — Orchestrator agent located in backend application namespace.
- `services/api/application/agent/rfp_department_workers.py` — Department workers (Warehouse, LastMile, Reverse) located in backend application namespace.
- `services/api/application/agent/rfp_synthesizer_agent.py` — Synthesizer agent located in backend application namespace.
- `services/api/application/agent/rfp_intake_pipeline.py` — LangGraph multi-agent pipeline and background runner `run_rfp_pipeline_background` located in backend application namespace.
- `services/api/presentation/api/v1/rfp.py:24,116` — FastAPI router directly importing `run_rfp_pipeline_background` from `application.agent.rfp_intake_pipeline`.
- `services/api/tests/unit/agent/test_rfp_*.py` — Unit tests importing agents from `application.agent.*`.
- `services/api/tests/integration/test_rfp_*.py` — Integration and quickstart E2E tests importing `RFPIntakePipeline` from `application.agent.rfp_intake_pipeline`.
- `uis/backoffice/app/rfp/[id]/page.tsx:3,18-20,29-31` — RFP ticket detail page importing and calling `use` from React 19 on a `Promise<params>` prop instead of React 18 / Next 14 compatible synchronous params.

## Root Cause Hypothesis

During the implementation of `031-rfp-intake`, the five agentic modules and the LangGraph graph were co-located with the FastAPI service under `services/api/application/agent/` instead of aligning with monorepo convention (`data/pipelines/`) where data and AI workflows reside (confidence: high). Simultaneously, the frontend detail page for RFP tickets was written using Next.js 15 / React 19 conventions (`params: Promise<{ id: string }>` unpacked with `use(params)`), whereas the workspace dependencies strictly pin Next.js 14.2.5 and React 18.3.1 (confidence: high).

## Proposed Remediation

**Preferred**:
1. **Relocate Pipeline & Agent Modules to `data/pipelines/rfp_intake/`**:
   - Create `data/pipelines/rfp_intake/` package with `__init__.py`.
   - Move the five modules into `data/pipelines/rfp_intake/`:
     - `rfp_classifier_agent.py`
     - `rfp_orchestrator_agent.py`
     - `rfp_department_workers.py`
     - `rfp_synthesizer_agent.py`
     - `rfp_intake_pipeline.py`
   - Update internal imports within `data/pipelines/rfp_intake/` to reference `data.pipelines.rfp_intake.*` or package-relative imports.
   - Expose `run_rfp_pipeline_background` and `RFPIntakePipeline` cleanly from `data/pipelines/rfp_intake/__init__.py`.
2. **Update Router & Background Dispatch**:
   - In `services/api/presentation/api/v1/rfp.py`, update import to:
     `from data.pipelines.rfp_intake import run_rfp_pipeline_background`
     (or `from data.pipelines.rfp_intake.rfp_intake_pipeline import run_rfp_pipeline_background`), preserving endpoint trigger behavior via FastAPI `BackgroundTasks`.
3. **Update Test Suites**:
   - Update imports in `services/api/tests/unit/agent/test_rfp_*.py` and `services/api/tests/integration/test_rfp_*.py` to import from `data.pipelines.rfp_intake`.
4. **Fix React 18 Compatibility in `uis/backoffice/app/rfp/[id]/page.tsx`**:
   - Remove `use` from the `react` import.
   - Change `RFPDetailPageProps` to define `params: { id: string }`.
   - Unpack `ticketId` directly with `params.id` (or utilize `useParams<{ id: string }>()` from `'next/navigation'`).
   - Ensure `npm run build` and `npm run typecheck` pass cleanly in `uis/backoffice`.

**Alternatives**:
- *Keep alias shim in `services/api/application/agent/`*: Leave thin re-exporting stubs in `services/api/application/agent/` forwarding to `data/pipelines/rfp_intake/` for backwards compatibility during migration, then clean up after tests pass.

**Files likely to change**:
- `data/pipelines/rfp_intake/__init__.py` (new)
- `data/pipelines/rfp_intake/rfp_classifier_agent.py` (relocated)
- `data/pipelines/rfp_intake/rfp_orchestrator_agent.py` (relocated)
- `data/pipelines/rfp_intake/rfp_department_workers.py` (relocated)
- `data/pipelines/rfp_intake/rfp_synthesizer_agent.py` (relocated)
- `data/pipelines/rfp_intake/rfp_intake_pipeline.py` (relocated)
- `services/api/presentation/api/v1/rfp.py`
- `services/api/tests/unit/agent/test_rfp_classifier.py`
- `services/api/tests/unit/agent/test_rfp_department_workers.py`
- `services/api/tests/unit/agent/test_rfp_orchestrator.py`
- `services/api/tests/unit/agent/test_rfp_synthesizer.py`
- `services/api/tests/integration/test_rfp_handoff_api.py`
- `services/api/tests/integration/test_rfp_quickstart_e2e.py`
- `uis/backoffice/app/rfp/[id]/page.tsx`

**Tests to add or update**:
- Run unit tests: `pytest services/api/tests/unit/agent/ -v`
- Run integration tests: `pytest services/api/tests/integration/test_rfp_intake_api.py services/api/tests/integration/test_rfp_handoff_api.py services/api/tests/integration/test_rfp_quickstart_e2e.py -v`
- Run backoffice frontend validation: `npm --prefix uis/backoffice run build`

## Risks & Considerations

- **Python Path in Services/Docker**: Verify that `data` is resolvable from `services/api` at runtime and inside test runners (`pytest.ini_options.pythonpath = [".", "..", "../.."]` already includes the monorepo root).
- **Residual Unused Files**: Remove or clean up leftover `.py` files in `services/api/application/agent/` once moved so duplicate logic does not diverge.
- **Frontend App Router Export Constraints**: In `uis/backoffice/app/knowledge/page.tsx`, non-default function export `submitKnowledgeQuery` was also detected which can trigger Next.js App Router constraint errors during `next build`. This should be monitored or made internal/moved if it interferes with the build.

## Open Questions

- None. Scope and target directory paths are fully specified in the request.
