# Implementation Plan: auth-frontend

**Branch**: `[N/A]` | **Date**: 2026-09-08 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/003-auth-frontend/spec.md)

**Input**: Feature specification from `/specs/003-auth-frontend/spec.md`

## Summary

Implement JWT-based authentication flows (login, registration, logout) and client-side route protection across Next.js applications in the monorepo, explicitly excluding the public website. Store tokens in `localStorage` and intercept API calls to include the token and handle 401 expirations globally.

## Technical Context

**Language/Version**: TypeScript 5.9+ / React (Next.js App Router)
**Primary Dependencies**: Next.js, Tailwind CSS
**Storage**: `localStorage` (for JWT token)
**Testing**: Manual UI verification
**Target Platform**: Web browsers
**Project Type**: Next.js Web Applications (`uis/backoffice`, excluding `uis/website`)
**Constraints**: Must use `localStorage` for tokens. Next.js middleware cannot be used for route protection since it cannot read `localStorage`. Public website must be unaffected.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
- Project principles respected. Tailwind CSS and Semantic HTML5 are used for UI. Strict TypeScript typing is maintained.

## Project Structure

### Documentation (this feature)

```text
specs/003-auth-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           
│   └── api.md           # Phase 1 output (API constraints)
└── quickstart.md        # Phase 1 output
```

### Source Code (repository root)

```text
uis/backoffice/
├── src/
│   ├── app/
│   │   ├── login/
│   │   │   └── page.tsx
│   │   ├── register/
│   │   │   └── page.tsx
│   │   ├── account/
│   │   │   └── profile/
│   │   │       └── page.tsx
│   │   └── layout.tsx         # Add Client-side route guard integration here
│   ├── components/
│   │   └── AuthGuard.tsx      # Client-side route protection component
│   └── lib/
│       ├── api.ts             # Centralized fetch wrapper (token injection & 401 handling)
│       └── auth.ts            # Token storage and logout utilities
```

**Structure Decision**: The implementation will be integrated into the existing `uis/backoffice` Next.js application. We will create reusable authentication utilities (`api.ts`, `auth.ts`) and a global `AuthGuard` client component to wrap protected layouts, ensuring the public `uis/website` remains untouched.

## Complexity Tracking

N/A
