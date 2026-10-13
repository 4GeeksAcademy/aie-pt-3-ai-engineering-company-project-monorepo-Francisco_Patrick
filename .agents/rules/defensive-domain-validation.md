# Defensive Domain Validation & Error Handling Guardrails

## Scope Definition
- **Scope Type:** `File-Pattern Based`
- **Target File Patterns:** `src/utils/**/*.ts`, `services/**/*.ts`, `packages/shared/**/*.ts`

---

## Behavioral Guardrails & Requirements

1. **Untrusted Input Sanitization:**
   - Any function processing incoming external data (order emails, carrier webhook payloads, form inputs, external API responses) MUST pass through defensive validation routines (e.g. `src/utils/validation.ts`).
   - Validate field types, required properties, and string lengths before passing data to core business logic.

2. **Safe Error Handling:**
   - Functions should avoid throwing raw, unhandled runtime exceptions (`throw new Error(...)`) when encountering invalid domain inputs.
   - Return explicit, structured result types (e.g., `{ success: false, error: string }` or `{ success: true, data: T }`) so calling code can handle errors gracefully.

3. **Entity Schema Preservation:**
   - Preserve and reuse domain entity interfaces defined in `src/types/entities.ts` and `@repo/shared-types`.
   - Do not mutate or bypass core entity property definitions.
