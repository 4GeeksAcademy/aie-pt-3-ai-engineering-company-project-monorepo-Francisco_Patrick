# Implementation Plan: Recuperación y cambio de contraseña (AUTH-03)

**Branch**: `004-password-reset` | **Date**: 2026-09-11 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/004-password-reset/spec.md)

**Input**: Feature specification from `/specs/004-password-reset/spec.md`

## Summary

Implementar los endpoints de backend (`services/api`) y vistas de frontend (`uis/backoffice/`) para los flujos de recuperación de contraseña olvidada (vía correo transaccional Resend), restablecimiento mediante token seguro de uso único con 30 minutos de vida y cambio de contraseña para usuarios autenticados. La arquitectura asegura protección anti-enumeración de usuarios, hashing de contraseñas, limitación de frecuencia (rate limiting) y auditoría de eventos de seguridad.

## Technical Context

**Language/Version**: TypeScript 5.9+, Node.js ES2020  
**Primary Dependencies**: Next.js App Router (`uis/backoffice`), Resend (servicios de correo), bcrypt/argon2 (hashing), crypto (tokens)  
**Storage**: Base de datos relacional para persistencia de `PasswordResetToken` (hashes SHA-256) y `SecurityAuditLog`  
**Testing**: Jest / Vitest para pruebas unitarias de endpoints API y React Testing Library para componentes  
**Target Platform**: Node.js backend (`services/api`) y Navegadores modernos (Web / Móvil vía `uis/backoffice`)  
**Project Type**: Monorepo Web Application (Backend API + Frontend Next.js Backoffice)  
**Performance Goals**: `< 1.5s` respuesta en `/auth/forgot-password`, delivery de correo en `< 60s`  
**Constraints**: 0% de secretos expuestos en código fuente, tokens invalidables tras primer uso o pasados 30 minutos  
**Scale/Scope**: Múltiples solicitudes concurrentes protegidas con rate limiting (max 5/hora por email)  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Strict TypeScript & Zero Implicit Any**: Todas las interfaces de peticiones, respuestas y modelos están fuertemente tipadas sin `any`.
- [x] **Defensive Domain Layer**: Los datos ingresados (emails, tokens, passwords) pasan validación exhaustiva antes de persistir o procesar.
- [x] **Pre-commit Integrity**: La solución incluirá pruebas y comandos de verificación tipológica de acuerdo con `AGENTS.md`.

## Project Structure

### Documentation (this feature)

```text
specs/004-password-reset/
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de decisiones técnicas (Phase 0)
├── data-model.md        # Entidades, lifecycle y modelos de datos (Phase 1)
├── quickstart.md        # Guía de validación end-to-end (Phase 1)
├── contracts/
│   └── api-contracts.md # Especificación de endpoints HTTP (Phase 1)
└── checklists/
    └── requirements.md  # Checklist de calidad de requisitos
```

### Source Code (repository root)

```text
services/api/
├── src/
│   ├── controllers/
│   │   └── authController.ts       # Handlers para forgot-password, reset-password, change-password
│   ├── services/
│   │   ├── authService.ts          # Lógica de negocio y hash de tokens
│   │   └── emailService.ts         # Integración con Resend SDK / Transaccional
│   ├── models/
│   │   └── passwordResetToken.ts   # Persistencia y verificación de tokens
│   └── middlewares/
│       └── rateLimiter.ts          # Rate limit para solicitudes de autenticación

uis/backoffice/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── forgot-password/page.tsx # Formulario email anti-enumeración
│   │   │   ├── reset-password/page.tsx  # Formulario token + nueva clave
│   │   │   └── login/page.tsx           # Enlace añadido "¿Olvidaste tu contraseña?"
│   │   └── account/
│   │       └── change-password/page.tsx # Formulario autenticado de cambio de clave
│   └── services/
│       └── authApi.ts                   # Cliente API de autenticación
```

**Structure Decision**: Aplicación monorepo dividida en backend API (`services/api`) y frontend Next.js App Router (`uis/backoffice`), compartiendo tipos mediante `@repo/shared-types` si es necesario.

## Complexity Tracking

> **Sin violaciones de la constitución que requieran justificación especial.**
