---
name: verify-type-and-build-integrity
description: Runs static TypeScript type checking and build validation commands across TrackFlow monorepo packages to ensure build health and zero compiler errors.
---

# Skill: Verify Type & Build Integrity

## Objective
Gather empirical evidence demonstrating that all TypeScript code across the monorepo complies strictly with `tsconfig.json` rules (`strict: true`), compiles cleanly to `dist/`, and contains zero static type or syntax errors.

---

## Inputs
- **`workspaceRoot`** (string): Absolute path to the workspace root directory.
- **`targetPackage`** (optional string): Specific sub-package or app directory (e.g. `packages/shared`, `uis/website`).

---

## Execution Steps

1. Navigate to `workspaceRoot`.
2. Run TypeScript type validation:
   ```bash
   npm run typecheck
   ```
3. Run project build script:
   ```bash
   npm run build
   ```
4. Verify build artifacts in `dist/` directory.

---

## Verifiable Acceptance Criteria

- [ ] **Criteria 1 (Zero Type Errors):** Command `npm run typecheck` exits with return code `0` and outputs zero `tsc` compilation errors.
- [ ] **Criteria 2 (Successful Build):** Command `npm run build` completes successfully and produces target output files in `dist/` (e.g. `dist/utils/manualTestApp.js`).
- [ ] **Criteria 3 (Strict Flags Compliance):** No `@ts-ignore`, `@ts-nocheck`, or implicit `any` diagnostics are present in static analysis.
