# Research & Technical Decisions: RFP Response Generation & Department Drafting Pipeline (Part 2 of 3)

**Feature Branch**: `feature/rfp-response-generation`  
**Date**: 2026-11-22  
**Status**: Completed  
**Spec Reference**: `specs/032-rfp-response-generation/spec.md`  

---

## 1. Executive Summary

This document captures the architectural research, dependency evaluations, trade-off analyses, and design decisions for **Feature 032: RFP Response Generation & Department Drafting Pipeline (Part 2 of 3)**.

Part 2 consumes the validated Part 1 handoff payload (`ticket_id`, RFP metadata, per-department `key_aspects`, and sales synthesis) directly from PostgreSQL via SQLModel repository abstractions. It coordinates dedicated department generator agents (`warehouse`, `lastmile`, `reverse`), parallel multi-dimensional evaluators (Readability, Relevance, and Compliance), an automated generator–evaluator feedback loop with a bounded iteration cap ($\le 3$ attempts), and compiles an immutable handoff package for Part 3 (Human Approvals & Document Assembly).

---

## 2. Technical Decisions & Trade-off Analysis

### Decision 1: Pipeline Orchestration & Architecture (LangGraph Subgraphs vs Monolithic Graph)

- **Context**: In Part 1, `rfp_intake_pipeline.py` defined a sequential/fan-out LangGraph pipeline. In Part 2, each active department (`warehouse`, `lastmile`, `reverse`) needs to generate text and then iteratively evaluate and revise independently without blocking or being blocked by other departments.
- **Alternatives Evaluated**:
  1. *Monolithic LangGraph with Global Iteration State*: All departments generate in one turn, all evaluate, and if any fails, the entire graph re-runs or uses complex global retry counters.
     - *Flaws*: If `warehouse` passes on attempt 1, but `lastmile` needs 2 revisions, `warehouse` would needlessly re-generate or require brittle conditional bypassing in global state.
  2. *Independent Department Subgraphs / Async Worker Loops*: The orchestrator inspects `departments_needed` from Part 1, launches an isolated generator-evaluator loop per active department concurrently (using `asyncio.gather` or concurrent ThreadPool), and joins results when all departments have either passed or reached the iteration limit.
     - *Advantages*: Clean department isolation, zero race conditions on database writes, independent revision counters, and predictable timeout containment.
- **Decision**: Adopt **Independent Department Generator-Evaluator Loops** coordinated by `RFPResponseGenerationPipeline` in `data/pipelines/rfp_response_generation/` and exposed via `services/api/application/agent/`.
- **Rationale**: Meets Spec FR-003, FR-006, and SC-006. Ensures that passing departments do not perform redundant LLM iterations, while departments requiring revisions iterate strictly within their own bounded scope.

---

### Decision 2: Multi-Dimensional Parallel Evaluation Engine

- **Context**: Spec FR-006 requires each generated department section to undergo parallel evaluation across three distinct dimensions: Readability, Relevance, and Compliance.
- **Alternatives Evaluated**:
  1. *Single Monolithic LLM Prompt for all 3 criteria*: One LLM call evaluates readability, relevance, and compliance simultaneously.
     - *Flaws*: LLMs frequently hallucinate compliance rule passes or overlook specific negative constraints (e.g., subtle return turnaround promises under 48 hours). Non-deterministic and fragile in automated testing.
  2. *Hybrid Modular Evaluator Architecture*:
     - **Dimension 1 (Readability)**: Deterministic readability calculation via `TextstatReadabilityAdapter` / `py-readability-metrics` evaluating Flesch Reading Ease (target 40–80) and reading grade levels.
     - **Dimension 2 (Relevance)**: Semantic check verifying that all department `key_aspects` and open questions identified in Part 1 are explicitly addressed in the draft.
     - **Dimension 3 (Compliance)**: Deterministic business rules engine inspecting the 5 strict rules defined in `trackflow-BRIEFING.es.md` (§5) with explicit regex/keyword heuristics and validation assertions:
       1. `RULE-CURRENCY`: Price quoted in USD for US (`client_country == "US"`) or EUR for Spain (`client_country == "ES"`).
       2. `RULE-SLA`: Explicit on-time delivery SLA percentage committed in proposal text.
       3. `RULE-RETURNS-TIME`: No return processing promised in under 48 hours (detects and fails strings like "24h", "24-48 horas", "24 horas", "same-day returns").
       4. `RULE-DISCOUNT-TIERS`: Volume discount table or tier breakdown included.
       5. `RULE-CARRIER-RATES`: Carrier negotiated base rates never revealed; only final client-facing rates.
- **Decision**: Adopt the **Hybrid Modular Evaluator Architecture**.
- **Rationale**: Guarantees 100% deterministic detection of critical business rule violations (SC-003, FR-008) while enabling fast, parallel execution across the 3 dimensions with zero test flakiness.

---

### Decision 3: Iteration Cap & Needs Human Review Escalation Strategy

- **Context**: Spec FR-009, FR-010, and FR-011 define the self-correcting feedback loop with a default limit of 2 revisions (max 3 total attempts per section). What happens when a section still fails evaluation after 3 attempts?
- **Alternatives Evaluated**:
  1. *Discard or Abort Ticket*: Mark ticket as `descartado` or raise an unhandled exception.
     - *Flaws*: Violates FR-012 ("The ticket MUST NOT be discarded or aborted when the iteration cap is reached"). Discarding an RFP after generating high-value drafts wastes commercial work.
  2. *Escalate Section and Ticket to `needs_human_review`*:
     - Retain the latest generated draft text.
     - Retain the complete, structured `EvaluationResult` with violated rule IDs and diagnostic feedback.
     - Mark the section status as `needs_human_review`.
     - Update ticket status to `needs_human_review`.
     - Include both passed sections and flagged sections in the Part 3 handoff payload, allowing human managers (Miguel Torres, Ana Whitfield, Carlos Vega, Sofía Ramos) to review and arbitrate in Part 3.
- **Decision**: Adopt **Graceful Escalation to `needs_human_review`**.
- **Rationale**: Fully compliant with `trackflow-BRIEFING.es.md` and Spec 032 FR-011 and FR-012. Preserves all generated artifacts for auditability and commercial review.

---

### Decision 4: Relational Persistence Model & SQLModel Schema Evolution

- **Context**: Part 1 established `IntakeTicketTable`, `RFPMetadataTable`, `DepartmentSectionTable`, and `IntakeHandoffPayloadTable` in `services/api/infrastructure/persistence/sqlmodel/models.py`. How should Part 2 drafts, evaluation iterations, and Part 3 handoff data be persisted in PostgreSQL?
- **Alternatives Evaluated**:
  1. *Direct Alteration of `DepartmentSectionTable`*: Add `draft_content`, `iteration`, `status`, and `evaluation_results` JSON column directly to `DepartmentSectionTable`.
     - *Advantages*: Reuses the primary key and foreign key relationships already established in Part 1. Matches the schema pattern in `trackflow-BRIEFING.es.md` §2.3 ("Persiste Ticket, metadatos RFP y DepartmentSection (al menos key_aspects en la Parte 1; borradores/evals/aprobaciones en partes posteriores)").
     - *Complemented with*: `Part3HandoffPayloadTable` to store the final immutable proposal handoff payload.
  2. *Separate Multi-Table Iteration Ledger*: Create `proposal_drafts`, `evaluation_logs`, etc.
     - *Flaws*: Over-complicates SQLModel migrations for a bounded 3-iteration process.
- **Decision**:
  - Extend `DepartmentSectionTable` with fields:
    - `draft_content`: Optional[str] (Markdown proposal section text)
    - `iteration`: int (default 0)
    - `status`: str (default "pending", transitions to "drafting", "under_evaluation", "passed", "needs_human_review")
    - `evaluation_results`: JSON list of historical `EvaluationResult` dictionaries
  - Add `Part3HandoffPayloadTable` (`part3_handoff_payloads`) storing `ticket_id`, `schema_version`, `overall_status`, `department_sections` JSON, and `created_at`.
  - Extend `TicketStatus` enum with:
    - `DRAFTING = "generando_borrador"`
    - `UNDER_EVALUATION = "en_evaluación"`
    - `NEEDS_HUMAN_REVIEW = "needs_human_review"`
- **Rationale**: Clean, backward-compatible extension directly fulfilling briefing §2.3 and Constitution Principle I/II.

---

### Decision 5: Knowledge Base & Vector Retrieval Governance

- **Context**: Generator agents may query company guidelines, packaging rules, and standard rate guidelines from the vector knowledge base (Qdrant).
- **Alternatives Evaluated**:
  1. *Direct Qdrant Client in Pipeline*: Import and instantiate `qdrant_client.QdrantClient`.
     - *Flaws*: Violates Constitution Principle VII ("Presentation controllers, FastAPI route handlers, and external scripts MUST NOT instantiate direct, unmanaged Qdrant clients or bypass repository interfaces").
  2. *Access through `VectorStorePort` / `QdrantVectorStoreAdapter` with Graceful Fallback*: Inject existing vector adapter port; if Qdrant is disabled or unavailable (e.g. offline unit test runner), fall back gracefully to standard briefing defaults.
- **Decision**: Adopt **Encapsulated Vector Adapter with Graceful Fallback**.
- **Rationale**: 100% compliant with Constitution Principle VII and ensures unit tests in `tests/pipelines/` run deterministically without requiring a live external Qdrant instance.

---

### Decision 6: Testing Strategy & Automated Verification

- **Context**: Spec FR-017 and SC-007 require tests in `tests/pipelines/` covering:
  - At least one department generator agent.
  - At least one department evaluator agent (with both passing and failing cases).
  - At least one focused compliance-failure test case (e.g. returns turnaround < 48 hours).
  - Iteration cap enforcement test verifying termination at attempt 3 with `needs_human_review`.
- **Decision**: Create `tests/pipelines/test_rfp_response_generation.py` using synthetic test fixtures matching `trackflow-request-1.pdf` (ModaViva Spain: EUR, warehouse + reverse) and `trackflow-request-2.pdf` (Luna Cosmetics US: USD, warehouse + lastmile).
- **Rationale**: Provides 100% automated coverage of all core requirements without external network dependencies.

---

## 3. Best Practices & Reference Patterns

- **FastAPI / Asynchronous Pipeline Triggering**:
  - `POST /api/v1/rfp/{ticket_id}/generate-proposal` returns HTTP 202 with `ProposalGenerationAcceptedResponse`.
  - Pipeline executes in `BackgroundTasks` without blocking the HTTP event loop.
  - Polling endpoint `GET /api/v1/rfp/{ticket_id}/generation-status` exposes real-time iteration and section states.
  - Handoff endpoint `GET /api/v1/rfp/{ticket_id}/part3-handoff` returns the completed Part 3 payload once generation finishes.
- **Defensive Error Handling**:
  - Global try-except around pipeline execution updates ticket status to `needs_human_review` with diagnostic error recording, preventing orphaned tickets.
- **Strict Typing**:
  - All contracts modeled with Pydantic v2 and TypeScript interfaces in `@repo/shared-types`.
