# Bug Fix: Backoffice Business Logic Suite Crash (Module not found)

- **Slug**: backoffice-business-logic-crash
- **Fixed**: 2026-10-15
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Copied `src/` into the Docker build container in `uis/Dockerfile` and mounted `./src:/app/src` in `docker-compose.yml`, resolving the missing `../../../../src/utils/filtering` import path when `/business-logic` compiles inside Docker.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `uis/Dockerfile` | modified | Added `COPY src/ ./src/` after `COPY packages/ ./packages/` so root business logic utilities exist at `/app/src/` |
| `docker-compose.yml` | modified | Added `- ./src:/app/src` volume mount to `ui` service for runtime file synchronization |
| `uis/backoffice/__tests__/business-logic-imports.test.ts` | added | Added unit tests verifying module resolution and execution of filtering, search, sorting, aggregation, and validation utilities |

## Diff Highlights

```diff
--- a/uis/Dockerfile
+++ b/uis/Dockerfile
@@ -4,6 +4,7 @@ WORKDIR /app
-# 1. Copy shared packages to satisfy @repo/shared-types monorepo references
+# 1. Copy shared packages and root business foundations to satisfy monorepo references
 COPY packages/ ./packages/
+COPY src/ ./src/
```

```diff
--- a/docker-compose.yml
+++ b/docker-compose.yml
@@ -11,6 +11,7 @@ services:
       - ./uis:/app/uis
       - ./packages:/app/packages
+      - ./src:/app/src
       - /app/uis/website/node_modules
```

## Tests Added or Updated

- `uis/backoffice/__tests__/business-logic-imports.test.ts` — Verifies resolution and execution of `filtering`, `search`, `sorting`, `aggregation`, and `validation` utility functions imported from `src/utils/`.

## Local Verification

- Commands run:
  - `npm test` in `uis/backoffice` → PASS: 7 test suites passed, 35 tests passed (including new `business-logic-imports.test.ts`).
  - `npx tsc --noEmit` in `uis/backoffice` → PASS: 0 TypeScript type errors under strict typing rules.

## Deviations from Assessment

None. The implementation followed the preferred remediation outlined in the assessment.

## Follow-ups

- Rebuild and restart the Docker container to apply the changes in the active container environment: `docker compose up -d --build ui`.
- Test access to `http://localhost:3001/business-logic` in the browser or via automated testing.
