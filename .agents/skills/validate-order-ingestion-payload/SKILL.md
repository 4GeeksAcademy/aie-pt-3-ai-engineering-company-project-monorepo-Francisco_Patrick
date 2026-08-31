---
name: validate-order-ingestion-payload
description: Validates incoming raw order email JSON or webhook payloads against TrackFlow domain validation rules before processing or storing.
---

# Skill: Validate Order Ingestion Payload

## Objective
Validate incoming untrusted order payload objects (parsed from emails or customer webhooks) against TrackFlow's domain validation routines in `src/utils/validation.ts`, ensuring malformed data is rejected safely before entering internal warehouse systems.

---

## Inputs
- **`payload`** (object/string): Raw JSON object or parsed string containing order data (e.g. `orderId`, `customerEmail`, `destinationAddress`, `warehouseId`, `items`).
- **`warehouseId`** (string): Warehouse identifier (`LA-01` or `ZRG-01`).

---

## Execution Steps

1. Import domain validation utilities from `src/utils/validation.ts` and entity types from `src/types/entities.ts`.
2. Pass `payload` through validation functions (e.g. `validateOrderPayload(payload)`).
3. Inspect structured validation response (`{ success: boolean, data?: Order, error?: string }`).
4. Log validation result or return actionable error messages to caller.

---

## Verifiable Acceptance Criteria

- [ ] **Criteria 1 (Valid Payload Output):** For valid inputs, returns `{ success: true, data: SanitizedOrder }` matching `Order` schema.
- [ ] **Criteria 2 (Invalid Payload Rejection):** For invalid inputs (missing SKU, negative quantity, invalid email format), returns `{ success: false, error: string }` with specific error details.
- [ ] **Criteria 3 (Zero Unhandled Exceptions):** Function execution completes without throwing unhandled JavaScript runtime exceptions (`throw new Error(...)`).
