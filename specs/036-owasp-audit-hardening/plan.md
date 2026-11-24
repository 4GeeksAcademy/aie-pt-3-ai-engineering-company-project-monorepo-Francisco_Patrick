# Implementation Plan: TrackFlow OWASP Top 10 Security Audit, Infrastructure Hardening, and Critical Remediation

**Branch**: `036-owasp-audit-hardening` | **Date**: 2026-11-25 | **Spec**: [specs/036-owasp-audit-hardening/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/spec.md)

**Input**: Feature specification from `/specs/036-owasp-audit-hardening/spec.md`

## Summary

Conduct a comprehensive security assessment of the TrackFlow monorepo (`frontend`, `backend`, and `agentic system`) and underlying host infrastructure against the **OWASP Top 10 (2021)** and baseline host security benchmarks. The technical approach executes a tri-track audit model separating standard backend and frontend risks from LLM-specific agentic vulnerabilities (prompt injections, excessive agency, tool IDOR, and cross-tenant leakage). All findings classified as Critical (including CORS misconfigurations, carrier secret handling, and unauthenticated root SSH exposure) will be remediated and verified with reproducible before-and-after artifacts. High-impact irreversible actions (return claims exceeding monetary thresholds and in-transit carrier changes) enforce strict human-in-the-loop authorization gates, guaranteeing complete alignment with GDPR (72-hour AEPD breach notification readiness) and CCPA/CPRA without regressing existing monorepo functionality.

## Technical Context

**Language/Version**: Python >= 3.14 (`services/api`), TypeScript >= 5.9 (`uis/`, `packages/`), Bash / POSIX Shell & PowerShell (Host & CI/CD verification)

**Primary Dependencies**: 
- Backend & Agentic: FastAPI >= 0.141.1, Pydantic >= 2.13.5, SQLModel >= 0.0.22, LangGraph >= 1.2.22, Qdrant Client >= 1.13.0, PyJWT >= 2.15.1
- Frontend: Next.js (App Router), React 18/19, Tailwind CSS
- Infrastructure: OpenSSH Server (`sshd_config`), UFW / iptables firewall

**Storage**: SQLite (`inventory.db`), TinyDB (`db.json`), Qdrant Vector DB (`trackflow_knowledge`), In-memory / File-backed Redacted Audit Registry

**Testing**: `pytest` & `pytest-cov` (Python unit/integration tests), `npm run typecheck` (`tsc --noEmit`), `npm run build` (Next.js production compilation), OpenSSH / UFW verification scripts

**Target Platform**: Linux host server (Debian/Ubuntu production runtime), Modern Web Browsers (Next.js client/SSR)

**Project Type**: Monorepo Web Service + Frontend Applications + Autonomous Agent Workflows + Host Infrastructure

**Performance Goals**: 
- Backend & Agentic: Guardrail evaluation latency < 50ms overhead per turn; deterministic offline security test suite execution < 30s
- Frontend: Core Web Vitals targets LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0 in production builds

**Constraints**: 
- 100% evaluation of the 10 OWASP Top 10 categories across 3 tracks (Backend, Frontend, Agentic)
- Zero `any` types and strict TypeScript compiler settings (`strict: true`, `noImplicitReturns`, `noUncheckedIndexedAccess`)
- Zero PII or credential leaks in logs; zero raw exception (`str(e)`) leaks in HTTP responses (Constitution Principle IV)
- Mandatory human authorization for return claims $> 100.00$ EUR and in-transit carrier reassignments
- Root SSH login rejected (`PermitRootLogin no`) and non-root operational user enforced

**Scale/Scope**: 
- 8 evaluated subsystems (CX support agent, carrier selection engine, return approval engine, return policy RAG KB, tracking API, real-time operations dashboard, B2B customer brand portals, host server)
- 30 discrete OWASP evaluation intersections with explicit verdicts and citations
- 0 unresolved critical findings prior to branch merge

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Initial Gate Status | Post-Design Re-evaluation | Notes / Compliance Strategy |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | **PASS** | **PASS** | Monorepo boundaries remain strictly intact. Frontends (`uis/`) consume backend functionality purely via HTTP REST APIs. Security models and policies live in domain/application layers. |
| **II. Public API Compatibility & Strict Contract Serialization** | **PASS** | **PASS** | All new security endpoints and modified handlers maintain explicit Pydantic `response_model` annotations, inject dependencies via FastAPI `Depends`, and use non-blocking async execution. |
| **III. Strict TypeScript & Static Type Safety** | **PASS** | **PASS** | All TypeScript changes in frontends and shared packages adhere to `tsconfig.json` flags with zero `any` annotations, explicit return types, and explicit `import type` statements. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | **PASS** | **PASS** | Core focus of the feature. Eliminates raw exception exposure (`str(e)`), masks customer PII and carrier credentials in logs, and enforces fail-closed access control on cross-customer/cross-brand queries. |
| **V. Performance-First Architecture & Core Web Vitals** | **PASS** | **PASS** | Security headers and input/output sanitation do not introduce blocking hydration or SSR delays; LCP $\le$ 1.0s and TBT $\le$ 200ms thresholds are maintained. |
| **VI. Test-First Development & Deterministic Verification Gates** | **PASS** | **PASS** | Deterministic unit and integration tests are defined for each OWASP category and critical finding. Zero merge allowed without passing `typecheck`, `build`, and `pytest`. |
| **VII. Vector Database & Qdrant SDK Governance** | **PASS** | **PASS** | Qdrant interactions remain isolated in infrastructure adapters. RAG input sanitization isolates retrieved vectors with `<external_context authority="passive_data">` to prevent indirect injection. |

## Project Structure

### Documentation (this feature)

```text
specs/036-owasp-audit-hardening/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── owasp-audit-matrix.schema.json
│   ├── host-hardening-baseline.schema.json
│   └── agent-guardrail-hitl.schema.json
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
services/api/
├── application/
│   └── services/
│       ├── agent_guardrails.py          # Input, authorization, context, and output guardrails
│       ├── agent_action_policies.py     # Return threshold (>100 EUR) & in-transit carrier gates
│       ├── support_agent_service.py     # CX LangGraph workflow orchestration
│       └── guardrail_observability.py   # Redacted audit logging & GDPR breach telemetry
├── domain/
│   └── agent/
│       ├── entities.py                  # Agent domain entities, session context, policy boundaries
│       └── ports.py                     # Guardrail & policy repository interfaces
├── presentation/
│   ├── api/v1/
│   │   ├── agent.py                     # Support agent REST & WebSocket routes
│   │   └── security_audit.py            # Audit findings & observability endpoints
│   └── dependencies.py                  # Dependency injection providers (Depends)
├── main.py                              # FastAPI composition root (CORS hardening & security middleware)
└── tests/
    ├── unit/
    │   ├── test_security_audit_matrix.py
    │   ├── test_agent_guardrails_authorization.py
    │   ├── test_agent_action_policies.py
    │   └── test_security_cors_configuration.py
    └── integration/
        └── test_host_hardening_verification.py

uis/
├── backoffice/                          # Real-time operations dashboard
└── website/                             # B2B brand portals and customer tracking UI

infra/
├── host/
│   ├── sshd_config.hardened             # Hardened SSH configuration (PermitRootLogin no)
│   ├── ufw_setup.sh                     # Host firewall configuration script (default deny)
│   └── permissions_setup.sh             # Strict secret file and directory permission setup
└── README.md                            # Infrastructure baseline documentation
```

**Structure Decision**: Monorepo with dedicated FastAPI service (`services/api`), Next.js client applications (`uis/`), and declarative infrastructure automation scripts (`infra/host/`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations. All design artifacts and implementation plans strictly uphold all Constitution principles.*
