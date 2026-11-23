# Bug Fix: RFP Intake Pipeline Relocation & React 18 Dynamic Route Fix

- **Slug**: rfp-pipeline-relocation-react18
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Relocated the five RFP intake agent and multi-agent pipeline modules from `services/api/application/agent/` to `data/pipelines/rfp_intake/` with a unified package export, and updated all callers across FastAPI presentation router and test suites. Resolved React 18 incompatibility in `uis/backoffice/app/rfp/[id]/page.tsx` by replacing the React 19 `use(params)` hook with synchronous App Router props, and made `submitKnowledgeQuery` in `uis/backoffice/app/knowledge/page.tsx` internal to satisfy Next.js page export constraints.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `data/pipelines/rfp_intake/__init__.py` | added | Package exports for `RFPIntakePipeline`, `run_rfp_pipeline_background`, agents, and workers |
| `data/pipelines/rfp_intake/rfp_classifier_agent.py` | added | Relocated from `services/api/application/agent/rfp_classifier_agent.py` |
| `data/pipelines/rfp_intake/rfp_department_workers.py` | added | Relocated from `services/api/application/agent/rfp_department_workers.py` |
| `data/pipelines/rfp_intake/rfp_intake_pipeline.py` | added | Relocated and updated internal imports to `data.pipelines.rfp_intake.*` |
| `data/pipelines/rfp_intake/rfp_orchestrator_agent.py` | added | Relocated from `services/api/application/agent/rfp_orchestrator_agent.py` |
| `data/pipelines/rfp_intake/rfp_synthesizer_agent.py` | added | Relocated from `services/api/application/agent/rfp_synthesizer_agent.py` |
| `services/api/application/agent/*` | removed | Cleaned up residual directory and files in backend namespace |
| `services/api/presentation/api/v1/rfp.py` | modified | Updated import of `run_rfp_pipeline_background` to `data.pipelines.rfp_intake` |
| `services/api/tests/unit/agent/test_rfp_classifier.py` | modified | Updated import to `data.pipelines.rfp_intake.rfp_classifier_agent` |
| `services/api/tests/unit/agent/test_rfp_department_workers.py` | modified | Updated import to `data.pipelines.rfp_intake.rfp_department_workers` |
| `services/api/tests/unit/agent/test_rfp_orchestrator.py` | modified | Updated import to `data.pipelines.rfp_intake.rfp_orchestrator_agent` |
| `services/api/tests/unit/agent/test_rfp_synthesizer.py` | modified | Updated import to `data.pipelines.rfp_intake.rfp_synthesizer_agent` |
| `services/api/tests/integration/test_rfp_handoff_api.py` | modified | Updated import to `data.pipelines.rfp_intake` |
| `services/api/tests/integration/test_rfp_quickstart_e2e.py` | modified | Updated import to `data.pipelines.rfp_intake` |
| `uis/backoffice/app/rfp/[id]/page.tsx` | modified | Removed `use` import and call; used synchronous `params: { id: string }` |
| `uis/backoffice/app/knowledge/page.tsx` | modified | Removed `export` from `submitKnowledgeQuery` to conform with Next.js App Router rules |

## Diff Highlights (optional)

```tsx
// uis/backoffice/app/rfp/[id]/page.tsx
- import React, { useEffect, useState, useCallback, use } from 'react';
+ import React, { useEffect, useState, useCallback } from 'react';

export interface RFPDetailPageProps {
-   params: Promise<{ id: string }>;
+   params: { id: string };
}

export default function RFPDetailPage({ params }: RFPDetailPageProps): React.ReactElement {
-   const resolvedParams = use(params);
-   const ticketId = resolvedParams.id;
+   const ticketId = params.id;
```

```python
# services/api/presentation/api/v1/rfp.py
- from application.agent.rfp_intake_pipeline import run_rfp_pipeline_background
+ from data.pipelines.rfp_intake import run_rfp_pipeline_background
```

## Tests Added or Updated

- `services/api/tests/unit/agent/test_rfp_classifier.py` — Verifies classification screening importing from `data.pipelines.rfp_intake`
- `services/api/tests/unit/agent/test_rfp_department_workers.py` — Verifies warehouse, last mile, and reverse workers importing from `data.pipelines.rfp_intake`
- `services/api/tests/unit/agent/test_rfp_orchestrator.py` — Verifies orchestrator scoping importing from `data.pipelines.rfp_intake`
- `services/api/tests/unit/agent/test_rfp_synthesizer.py` — Verifies synthesizer policy checks importing from `data.pipelines.rfp_intake`
- `services/api/tests/integration/test_rfp_handoff_api.py` — Verifies RFP handoff endpoints with relocated pipeline
- `services/api/tests/integration/test_rfp_quickstart_e2e.py` — Verifies Quickstart E2E Scenarios 1, 2, and 3 with relocated pipeline

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/unit/agent/ services/api/tests/integration/test_rfp_handoff_api.py services/api/tests/integration/test_rfp_quickstart_e2e.py -v` → 16 passed, 0 failed in 1.78s
  - `npm.cmd --prefix uis/backoffice run build` → Next.js 14.2.35 production build compiled successfully, typecheck passed, 22/22 pages generated
- Manual checks: Verified `git grep "application.agent"` returns zero source code occurrences.

## Deviations from Assessment

None. The implementation closely followed the preferred remediation and resolved the build constraint in `uis/backoffice/app/knowledge/page.tsx` noted under Risks & Considerations.

## Follow-ups

- Proceed to `/speckit-bug-test slug=rfp-pipeline-relocation-react18` to generate the verification report.
