# Implementation Plan: Backoffice Inventory Management Interface

**Branch**: `011-backoffice-inventory-ui` | **Date**: 2026-09-17 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/011-backoffice-inventory-ui/spec.md)

**Input**: Feature specification from `/specs/011-backoffice-inventory-ui/spec.md`

## Summary

Build the backoffice inventory management views in Next.js (`uis/backoffice`) enabling authenticated operational staff to view live product stock levels across warehouses (`wh-la`, `wh-zgz`), register inbound deliveries (`POST /inventory/orders/inbound`), log outbound stock exits (`POST /inventory/orders/outbound`), and review a read-only historical orders ledger (`GET /inventory/orders`). A centralized API client layer (`uis/backoffice/lib/inventory.ts`) encapsulates all HTTP communication using `fetchWithAuth`, enforcing `Authorization: Bearer <token>`, reactive stock validation, visual health status indicators, inline error handling, and strict route authentication guards across all four pages.

## Technical Context

**Language/Version**: TypeScript 5.x (Strict typing enabled, `noImplicitAny: true`)

**Primary Dependencies**: Next.js 14+ (App Router), React 18, Tailwind CSS, Lucide React (Icons)

**Storage**: Web `localStorage` (`auth_token` authentication key)

**Testing**: Jest + React Testing Library (`npm test` in `uis/backoffice`)

**Target Platform**: Desktop Web Browsers (Chrome, Firefox, Edge)

**Project Type**: Next.js Web Application (`uis/backoffice`)

**Performance Goals**: Sub-300ms reactive stock status updates; zero unhandled promise rejections or silent API error failures.

**Constraints**: Strict TypeScript with explicit return type annotations and type-only imports; zero direct `fetch` calls in components; domain language matching `CONTEXT.md` (`SKU`, `wh-la`, `wh-zgz`, `user_uuid`).

**Scale/Scope**: 4 inventory routes (`/inventory/products`, `/inventory/orders/inbound`, `/inventory/orders/outbound`, `/inventory/orders`), 1 API client module (`lib/inventory.ts`), 4 core UI components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Rule I: Strict TypeScript Typing**: All files in `uis/backoffice/lib/inventory.ts` and `app/inventory/**` must have zero `any` types, explicit function return types, and explicit type imports (`import type { ... }`). -> **PASS**
- **Rule II: No Swallowed API Errors**: `lib/inventory.ts` must parse `4xx`/`5xx` JSON error bodies (`detail` / `message`) and propagate explicit typed errors for UI components to render visibly. -> **PASS**
- **Rule III: Route Protection**: All 4 inventory routes MUST enforce client authentication (`AuthGuard` / token checks). -> **PASS**
- **Rule IV: Domain Vocabulary**: Entities and labels must mirror `CONTEXT.md` (`wh-la`, `wh-zgz`, `SKU`, `user_uuid`). -> **PASS**

## Project Structure

### Documentation (this feature)

```text
specs/011-backoffice-inventory-ui/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Technical decisions & rationale
├── data-model.md        # TypeScript interfaces & domain schemas
├── quickstart.md        # Runnable verification scenarios
└── contracts/           # API contract specification
    └── inventory-api-contract.md
```

### Source Code (repository root)

```text
uis/backoffice/
├── lib/
│   ├── api.ts                         # Existing fetchWithAuth utility
│   ├── auth.ts                        # Existing token management (getToken, isAuthenticated)
│   └── inventory.ts                   # [NEW] Centralized API client module for /inventory
├── components/
│   ├── AuthGuard.tsx                  # Existing route protection wrapper
│   ├── Header.tsx                     # Navigation header (add Inventory links)
│   └── inventory/
│       ├── StockStatusBadge.tsx       # [NEW] Visual indicator component for stock levels
│       ├── ProductTable.tsx           # [NEW] Table listing products with current_stock & actions
│       ├── InboundOrderForm.tsx       # [NEW] Inbound delivery submission form
│       ├── OutboundOrderForm.tsx      # [NEW] Outbound stock exit form with reactive guard
│       └── OrdersHistoryTable.tsx     # [NEW] Read-only audit ledger table
└── app/
    └── inventory/
        ├── products/
        │   └── page.tsx               # [NEW] /inventory/products page
        ├── orders/
        │   ├── page.tsx               # [NEW] /inventory/orders history page
        │   ├── inbound/
        │   │   └── page.tsx           # [NEW] /inventory/orders/inbound form page
        │   └── outbound/
        │       └── page.tsx           # [NEW] /inventory/orders/outbound form page
```

**Structure Decision**: Standardized Next.js App Router structure under `uis/backoffice/app/inventory/` and components under `uis/backoffice/components/inventory/`. Centralized API logic isolated in `uis/backoffice/lib/inventory.ts`.

## Complexity Tracking

> **No violations found. Design adheres strictly to repository patterns and constitution rules.**
