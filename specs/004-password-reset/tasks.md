# Tasks: Recuperación y cambio de contraseña (AUTH-03)

**Input**: Design documents from `/specs/004-password-reset/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Format: `- [ ] [TaskID] [P?] [Story?] Description with exact file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure setup

- [x] T001 Verify and update environment configuration variables in `services/api/.env.example` to document `RESEND_API_KEY` and token expiration settings.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure and data types that MUST be complete before ANY user story can be implemented

- [x] T002 Define TypeScript domain types for PasswordResetToken, AuditLog, and API request/response payloads in `packages/shared/src/types/auth.ts`.
- [x] T003 [P] Implement database repository or in-memory persistence layer for PasswordResetToken with SHA-256 token hashing and expiration validation in `services/api/src/models/passwordResetToken.ts`.
- [x] T004 [P] Implement security audit logging service in `services/api/src/services/auditService.ts`.
- [x] T005 [P] Implement rate limiting middleware for auth endpoints (5 requests/hour per email) in `services/api/src/middlewares/rateLimiter.ts`.
- [x] T006 Implement transactional email delivery service with Resend SDK integration and HTML template support in `services/api/src/services/emailService.ts`.

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Solicitud de Restablecimiento de Contraseña (Priority: P1) 🎯 MVP

**Goal**: Permitir al usuario solicitar un enlace de restablecimiento vía email sin revelar si la cuenta existe (anti-enumeración).

**Independent Test**: Enviar solicitud desde `/forgot-password` con correos existentes y no existentes; ambos deben devolver 200 OK y la misma respuesta en UI, emitiendo el correo solo para el existente.

- [x] T007 [P] [US1] Implement `POST /auth/forgot-password` controller and service in `services/api/src/controllers/authController.ts` and `services/api/src/services/authService.ts`.
- [x] T008 [P] [US1] Create frontend API client method `requestPasswordReset` in `uis/backoffice/src/services/authApi.ts`.
- [x] T009 [US1] Create `/forgot-password` page component with form disabling and anti-enumeration feedback in `uis/backoffice/src/app/(auth)/forgot-password/page.tsx`.
- [x] T010 [US1] Add visible "¿Olvidaste tu contraseña?" link pointing to `/forgot-password` in `uis/backoffice/src/app/(auth)/login/page.tsx`.

**Checkpoint**: User Story 1 fully functional and testable independently.

---

## Phase 4: User Story 2 - Restablecimiento de Contraseña desde Enlace (Priority: P2)

**Goal**: Permitir al usuario definir una nueva contraseña utilizando un token válido de 30 minutos recibido por correo e invalidarlo tras su uso.

**Independent Test**: Navegar a `/reset-password?token=<token_válido>`, enviar nueva clave, verificar redirección a `/login` e intentar reutilizar el token (debe fallar con 400 Bad Request).

- [x] T011 [P] [US2] Implement `POST /auth/reset-password` controller and service logic in `services/api/src/controllers/authController.ts` and `services/api/src/services/authService.ts`.
- [x] T012 [P] [US2] Create frontend API client method `resetPassword` in `uis/backoffice/src/services/authApi.ts`.
- [x] T013 [US2] Create `/reset-password` page component reading `token` from URL query string with validation and error handling in `uis/backoffice/src/app/(auth)/reset-password/page.tsx`.

**Checkpoint**: User Stories 1 and 2 work independently and end-to-end.

---

## Phase 5: User Story 3 - Cambio de Contraseña Autenticado (Priority: P3)

**Goal**: Permitir a usuarios autenticados cambiar su contraseña previa desde su panel de cuenta.

**Independent Test**: Desde `/account/change-password`, enviar contraseña actual errónea (rechazo 400) y luego contraseña correcta (éxito 200).

- [x] T014 [P] [US3] Implement `POST /auth/change-password` authenticated controller and service logic in `services/api/src/controllers/authController.ts` and `services/api/src/services/authService.ts`.
- [x] T015 [P] [US3] Create frontend API client method `changePassword` in `uis/backoffice/src/services/authApi.ts`.
- [x] T016 [US3] Create `/account/change-password` page component with current password and match validation in `uis/backoffice/src/app/account/change-password/page.tsx`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificación final, pruebas integradas y documentación

- [x] T017 Execute end-to-end quickstart validation scenarios defined in `specs/004-password-reset/quickstart.md`.
- [x] T018 Run TypeScript static typecheck (`npm run typecheck`) and linting across `services/api` and `uis/backoffice`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories.
- **User Stories (Phases 3-5)**: Depend on Foundational completion. Sequential execution in priority order (US1 → US2 → US3) or in parallel per story.
- **Polish (Phase 6)**: Depends on completion of all user stories.

### User Story Dependencies

- **User Story 1 (P1)**: Independent after Foundational.
- **User Story 2 (P2)**: Independent, consumes token generated by US1 backend logic.
- **User Story 3 (P3)**: Independent authenticated flow.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Setup (Phase 1) & Foundational (Phase 2).
2. Complete User Story 1 (Phase 3).
3. Validate anti-enumeration and email delivery.

### Full Delivery
1. Complete User Story 2 (Phase 4) and User Story 3 (Phase 5).
2. Execute Phase 6 Polish & quickstart scenarios.
