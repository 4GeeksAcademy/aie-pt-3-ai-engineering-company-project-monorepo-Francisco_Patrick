# Bug Assessment: Backoffice Business Logic Suite Crash (Module not found)

- **Slug**: backoffice-business-logic-crash
- **Created**: 2026-10-15
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user reported that navigating to the Backoffice UI and clicking on `[Abrir Business Logic Suite →](http://localhost:3001/business-logic)` crashes the Backoffice application completely.

### Verbatim Error Trace
```text
⨯ ./app/business-logic/page.tsx:4:1
Module not found: Can't resolve '../../../../src/utils/filtering'
2 |
3 | import React, { useState } from 'react';
> 4 | import { filterCarriers, filterReturnRequests, filterShipments } from '../../../../src/utils/filtering';
| ^
5 | import { binarySearchIndexByField, linearSearchIndex } from '../../../../src/utils/search';
6 | import { sortByField, sortByMultipleFields } from '../../../../src/utils/sorting';
7 | import {
https://nextjs.org/docs/messages/module-not-found
```

### URL Policy Record
- **URL 1**: `http://localhost:3001/business-logic`
  - **Host**: `localhost`
  - **Action**: `auto-refused: loopback host (RFC 1918 / localhost security policy)`
- **URL 2**: `https://nextjs.org/docs/messages/module-not-found`
  - **Host**: `nextjs.org`
  - **Action**: `fetch skipped: generic framework documentation link in error trace`

## Symptom

When accessing the Business Logic Suite (`/business-logic`) on port 3001 in Docker, Next.js fails to compile `./app/business-logic/page.tsx` because it cannot resolve `../../../../src/utils/filtering`. The application renders an unhandled exception / 500 error screen instead of the interactive execution dashboard.

Expected behavior: The `/business-logic` route compiles successfully, renders the `LogicRunnerPanel` and `OutputViewer`, and executes the business logic functions with sample data.

## Reproduction

1. Run the containerized environment: `docker compose up`.
2. Open the Backoffice web application in the browser at `http://localhost:3001`.
3. In the entry dashboard (`app/page.tsx`), click the link `[Abrir Business Logic Suite →](http://localhost:3001/business-logic)` or navigate directly to `http://localhost:3001/business-logic`.
4. Observe the Next.js compilation error `Module not found: Can't resolve '../../../../src/utils/filtering'` crashing the view.

## Suspected Code Paths

- [uis/backoffice/app/business-logic/page.tsx:4-20](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/app/business-logic/page.tsx#L4-L20) — Imports business logic utilities directly from `../../../../src/utils/*`, expecting `src/` to exist 4 directory levels up (i.e. `/app/src` inside the container).
- [uis/Dockerfile:6-19](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/Dockerfile#L6-L19) — Dockerfile only copies `packages/` and `uis/` into `/app`. It omits copying `src/`.
- [docker-compose.yml:10-16](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml#L10-L16) — Volumes for the `ui` service mount `./uis:/app/uis` and `./packages:/app/packages`, but do not mount `./src:/app/src`.
- [uis/backoffice/tsconfig.json:29-37](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/tsconfig.json#L29-L37) — Path mappings only include `@/*` and `@repo/shared-types`, without explicit monorepo aliases for root `src/`.

## Root Cause Hypothesis

**Confidence: High**

The Backoffice page `uis/backoffice/app/business-logic/page.tsx` adheres to Milestone 2 / SPEC specification by directly importing TypeScript logic algorithms from the monorepo root directory via relative paths (`../../../../src/utils/...`).

On the developer's host machine, `src/utils/` exists and TypeScript compilation succeeds. However, inside the Docker container created by `uis/Dockerfile` and orchestrated via `docker-compose.yml`:
1. The container file system only contains `/app/packages` and `/app/uis`. The root `/src` directory was never copied during `docker build`.
2. The runtime volume mounts in `docker-compose.yml` only mount `./uis` and `./packages`. Therefore, at runtime, `/app/src` does not exist inside the container.
3. When Next.js attempts to resolve `../../../../src/utils/filtering` from `/app/uis/backoffice/app/business-logic/page.tsx`, the target path `/app/src/utils/filtering` is missing, causing Next.js bundler to throw a fatal `Module not found` error.

## Proposed Remediation

**Preferred**:
1. Update [uis/Dockerfile](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/Dockerfile):
   - Add `COPY src/ ./src/` (or `COPY src/ /app/src/`) alongside `COPY packages/ ./packages/` so that the root business logic files are present in the Docker image.
2. Update [docker-compose.yml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml):
   - Add `- ./src:/app/src` under `services.ui.volumes` so live code updates in `src/` are immediately mirrored into the container.
3. Validate [uis/backoffice/next.config.mjs](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/next.config.mjs):
   - Ensure Next.js allows compiling files outside the project root without restrictions (Next.js 14 handles external relative imports by default if files are physically present).

**Alternatives**:
- *Package Migration*: Move `src/utils` and `src/types` into a dedicated workspace package (e.g., `packages/business-logic` or within `packages/shared`), and expose it via `@repo/business-logic` or `@repo/shared-types`.
  *Trade-off*: Cleaner long-term monorepo packaging, but deviates from the explicit Milestone 2 specification (`Direct Monorepo Module Import` from `src/utils`) and requires updating import statements across multiple files and tests.

**Files likely to change**:
- `uis/Dockerfile`
- `docker-compose.yml`
- (Optional) `uis/backoffice/tsconfig.json` (if alias convenience is added)

**Tests to add or update**:
- Automated test or build verification checking that `uis/backoffice` can build (`npm run build`) and resolve all imports without missing module errors.
- Verification inside Docker container (`docker compose exec ui test -d /app/src/utils`) and checking HTTP status 200 on `http://localhost:3001/business-logic`.

## Risks & Considerations

- Rebuilding Docker containers: After updating `uis/Dockerfile` and `docker-compose.yml`, the `ui` service image must be rebuilt (`docker compose build ui` or `docker compose up -d --build ui`) for changes to take effect.
- File synchronization: Mounting `./src:/app/src` in Windows/WSL2 Docker Compose requires ensuring volume mounts do not have permission or case-sensitivity issues.

## Open Questions

- None. The root cause is clearly reproducible and confirmed via codebase inspection.
