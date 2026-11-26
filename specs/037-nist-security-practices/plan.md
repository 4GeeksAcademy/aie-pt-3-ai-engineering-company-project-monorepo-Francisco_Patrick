# Implementation Plan: NIST Security Practices & AI Governance Baseline

**Branch**: `037-nist-security-practices` | **Date**: 2026-11-25 | **Spec**: [specs/037-nist-security-practices/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/037-nist-security-practices/spec.md)

**Input**: Feature specification from `specs/037-nist-security-practices/spec.md`

---

## Summary

TrackFlow Tech operates an AI-augmented logistics intelligence platform across Los Angeles (USA) and Zaragoza (Spain). This feature establishes an authoritative AI security and governance baseline aligned with the **NIST Cybersecurity Framework (CSF) 2.0**, **OWASP Top 10 for LLM Applications (2025/2026)**, the **EU General Data Protection Regulation (GDPR / RGPD UE 2016/679)**, and the **California Consumer Privacy Act / California Privacy Rights Act (CCPA/CPRA)**.

Key implementations include:
1. Authoritative AI Systems Inventory (`AISystemRecord`) across all 5 operational AI components with designated internal custodians and attack surface mapping.
2. Third-Party AI Provider Shared Responsibility Matrix (`SharedResponsibilityRecord`).
3. Transatlantic regulatory compliance mapping, featuring an automated containment and notification protocol for the GDPR 72-hour AEPD incident notification SLA and CCPA/CPRA consumer privacy rights.
4. Prompt boundary isolation using structural delimiters (`<<<EXTERNAL_UNTRUSTED_CONTENT>>>`) and automated regression tests neutralizing direct and indirect prompt injection attacks.
5. In-application rate limiting on LLM-triggering endpoints (HTTP 429) to prevent denial-of-wallet and unbounded execution loops.
6. Execution guardrails enforcing output schema validation and tool allowlisting.
7. Human-in-the-Loop (HITL) authorization gates and tamper-evident audit logging for the four defined irreversible operational actions.
8. Authoritative 6-function NIST CSF 2.0 assessment report (Govern, Identify, Protect, Detect, Respond, Recover) with an active residual risk ledger.

---

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.x (target ES2022)  
**Primary Dependencies**: FastAPI (>=0.100.0), Pydantic v2 (>=2.0.0), LangGraph (>=1.2.22), LangChain MCP Adapters (>=0.3.2), Qdrant Client (>=1.13.0), Pytest (>=7.0.0)  
**Storage**: SQLite (`inventory.db`), TinyDB (`db.json`), In-memory thread-safe review queue (`AgentActionPoliciesService`), JSON specification artifacts (`specs/037-nist-security-practices/`)  
**Testing**: `uv run pytest` (unit, integration, and contract test suites)  
**Target Platform**: Linux (Ubuntu 22.04 LTS / Debian containerized host) and Windows development environment  
**Project Type**: Multi-tier Web Service (FastAPI) + Documentation & Governance Registry  
**Performance Goals**: Guardrail / prompt boundary isolation overhead < 15ms p95; rate limit rejection < 5ms (HTTP 429); Qdrant vector retrieval < 100ms  
**Constraints**: Zero hardcoded secrets, deterministic NIST CSF 6-function mapping, 100% compliance with GDPR 72-hour AEPD notification SLA and CCPA/CPRA, thread-safe HITL queue for 4 irreversible actions  
**Scale/Scope**: 5 AI systems, 8 courier carrier integrations, 4 irreversible operational action gates, 6 NIST CSF functions, 30+ audited security controls  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Compliance Status | Justification / Implementation Evidence |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries preserved; `domain/`, `application/`, `infrastructure/`, `presentation/` separation strictly enforced. | **PASS** | Domain entities in `domain/agent/`, orchestration in `application/services/`, REST controllers in `presentation/api/v1/`. Zero direct frontend DB imports. |
| **II. Public API Compatibility & Strict Serialization** | Explicit Pydantic `response_model`, typed parameters, dependency injection via `Depends`, async non-blocking execution, zero PII or internal model leakage. | **PASS** | Governance endpoints (`/api/v1/security-audit/nist-csf`, `/api/v1/security-audit/ai-inventory`, `/api/v1/agent/actions/review`) enforce explicit Pydantic response models and inject data providers via `Depends`. |
| **III. Strict TypeScript & Type Safety** | Strict compiler flags, zero `any`, explicit return types, explicit type imports (`import type`). | **PASS** | Shared contracts and UI types comply with workspace `tsconfig.json`. |
| **IV. Defensive Error Handling & Zero Data Leaks** | Zero raw error exposure (`str(e)` in 500 banned), zero PII/credentials in logs, no swallowed failures, fail-fast secret checks. | **PASS** | `GuardrailObservabilityService` masks PII and carrier tokens; exception handlers return sanitized error payloads; missing secrets trigger fast initialization failure. |
| **V. Performance-First Architecture** | Core Web Vitals thresholds (LCP ≤ 1.0s, TBT ≤ 200ms), no blocking SSR hydration guards. | **PASS** | Rate limit checks and boundary isolation run in-memory with sub-15ms overhead, adding zero frontend bundle bloat. |
| **VI. Test-First Development & Deterministic Gates** | Unit and integration test coverage with `pytest`, deterministic verification gates. | **PASS** | Comprehensive automated test suites in `services/api/tests/unit` and `services/api/tests/integration` verify prompt injection defenses, rate limiting, and HITL gates. |
| **VII. Vector DB & Qdrant SDK Governance** | Encapsulated vector adapters, canonical collections, typed payloads, confidence guardrails, source citations. | **PASS** | RAG retrieval in `knowledge_service.py` is abstracted through repository ports with confidence thresholds and citations. |

*Verdict: 100% PASS. Zero constitutional violations. No complexity exception grants required.*

---

## Project Structure

### Documentation & Specifications (this feature)

```text
specs/037-nist-security-practices/
├── plan.md              # This implementation plan
├── research.md          # Phase 0 research findings and architectural decisions
├── data-model.md        # Phase 1 data entities, schemas, and sequence flows
├── quickstart.md        # Phase 1 runnable validation scenarios
├── contracts/           # Phase 1 schema and API contracts
│   ├── nist-security-schemas.json           # JSON Schema for domain entities & reports
│   └── nist-governance-api.openapi.json     # OpenAPI 3.1 REST contracts
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
services/api/
├── domain/
│   └── agent/
│       ├── entities.py                      # AISystemRecord, SharedResponsibilityRecord, HITLApprovalRequest, ResidualRiskRecord
│       └── exceptions.py                    # SecurityGuardrailException, RateLimitExceededException
├── application/
│   └── services/
│       ├── agent_action_policies.py         # HITL Gate service governing 4 irreversible actions
│       ├── agent_guardrails.py              # Prompt boundary delimiter & output validation allowlist
│       ├── support_agent_service.py         # 24/7 CX Agent orchestrator with rate-limiting & boundary isolation
│       ├── carrier_service.py               # Carrier selection engine with indirect injection neutralization
│       ├── knowledge_service.py             # Return policy & SLA RAG vector retriever
│       └── guardrail_observability.py       # PII/token redaction & structured audit logging
├── presentation/
│   ├── api/
│   │   └── v1/
│   │       ├── security_audit.py            # Endpoints: /nist-csf, /ai-inventory, /shared-responsibility, /residual-risks
│   │       └── agent.py                     # Endpoint: /actions/review (HITL supervisor review)
│   ├── dependencies.py                      # Dependency injection providers for security & audit services
│   └── schemas/
│       └── security_audit.py                # Pydantic v2 DTOs matching contracts/nist-security-schemas.json
└── tests/
    ├── unit/
    │   ├── test_agent_action_policies.py    # Tests for 4 irreversible action gates
    │   ├── test_agent_guardrails_input.py   # Direct prompt injection neutralization tests
    │   ├── test_agent_guardrails_output.py  # Output schema allowlist validation tests
    │   ├── test_carrier_indirect_injection.py # Warehouse note indirect injection tests
    │   ├── test_nist_ai_inventory.py        # AI systems inventory schema tests
    │   └── test_nist_shared_responsibility.py # Third-party vendor shared responsibility tests
    └── integration/
        ├── test_rate_limiting_guardrail.py  # HTTP 429 rate limiting integration tests
        └── test_nist_csf_report_api.py      # 6-function NIST CSF report & GDPR 72h SLA endpoint tests
```

**Structure Decision**: Monorepo layered architecture adhering to Constitution Principle I and II. All backend domain rules, guardrail services, and presentation routers reside within `services/api/`. Specifications and audit contract schemas reside in `specs/037-nist-security-practices/`.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations. All architectural patterns align with existing monorepo design principles.*
