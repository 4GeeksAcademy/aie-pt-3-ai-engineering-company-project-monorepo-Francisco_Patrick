---
trigger: always_on
---

# Strict TypeScript & Zero Implicit Any Rule

## Scope Definition
- **Scope Type:** `Always Active (Global Workspace)`
- **Target File Patterns:** `**/*.ts`, `**/*.tsx`

---

## Behavioral Guardrails & Requirements

1. **Compiler Flags Adherence:**
   - All TypeScript files must strictly comply with the settings defined in `tsconfig.json` (`strict: true`, `noImplicitReturns`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`).

2. **No `any` Types or Type Suppression:**
   - Never use `any` as a type annotation. Use precise interfaces, type aliases, or generics.
   - Do not use unsafe type assertions (e.g. `as unknown as Type`).
   - Do not use `@ts-ignore`, `@ts-nocheck`, or `@ts-expect-error` to suppress compiler errors unless explicitly authorized by a developer.

3. **Explicit Annotations & Documentation:**
   - All exported functions, methods, and classes must have explicit return type annotations.
   - All exported functions must include JSDoc comments detailing parameter meanings, expected ranges, and potential failure return states.

4. **Explicit type imports:**
   - All imported types must be defined as a type (e.g., import type { typeName} from `pathName` or import { type typeName, otherFunction} from `pathName`)