# Feature Specification: RFP Response Generation & Department Drafting Pipeline (Part 2 of 3)

**Feature Branch**: `feature/rfp-response-generation`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Continuation of Spec 031-rfp-intake: AC-1 Part 1 Routing Handoff & Entry State; AC-2 Per-Department Proposal Draft Generation; AC-3 Parallel Evaluation & Structured EvaluationResult; AC-4 Generator–Evaluator Feedback Loop & Iteration Cap; AC-5 Ticket Lifecycle & PostgreSQL Persistence; AC-6 Part 3 Handoff; AC-7 Unit Tests"

## Clarifications & Design Decisions

### Session 2026-11-22

- **Q1: Part 1 Routing Handoff Ingestion**: How does Part 2 consume the output of Part 1?
  - **Resolution**: Part 2 strictly consumes the validated Part 1 handoff payload (`ticket_id`, RFP metadata, and per-department `key_aspects` / open questions / workstreams) from PostgreSQL. It does not re-read or re-parse the raw PDF as primary input, nor does it reset or overwrite the initial `intake_complete` (`analisis_completo`) ticket state until drafting commences.
- **Q2: Evaluation Parallelism & State Concurrency**: How do parallel department evaluations prevent race conditions or database write locks?
  - **Resolution**: Evaluations execute per active department independently and concurrently. Results are written per `DepartmentSection` (keyed by `ticket_id` and `department_id`), avoiding shared global state conflicts. Readability, relevance, and compliance checks within a department run simultaneously.
- **Q3: Iteration Cap & Escalation**: What is the default maximum iteration cap for the generator–evaluator loop, and what happens when reached?
  - **Resolution**: The default iteration limit is 2 revisions (max 3 total generation attempts per section). If a section fails evaluation after exhausting its limit, the workflow does not discard the ticket or abort the pipeline; it retains the latest draft along with the detailed `EvaluationResult`, marks the section/ticket with `needs_human_review`, and packages both passed and flagged sections into the Part 3 handoff payload.
- **Q4: Ticket Status Terminology**: How are English and Spanish status identifiers reconciled?
  - **Resolution**: In alignment with `docs/agentic-workflows/trackflow-BRIEFING.es.md` and Spec 031, canonical ticket statuses support both English and Spanish representations: `drafting` (`generando_borrador`), `under_evaluation` (`en_evaluación`), and `needs_human_review`. Part 3 approval statuses (`esperando_aprobación` / `waiting_for_approval` and `terminado` / `done`) are strictly out of scope for Part 2.
- **Q5: Compliance Rule Enforcement**: What specific business rules must the compliance evaluator verify?
  - **Resolution**: Evaluates the 5 mandatory business rules in `trackflow-BRIEFING.es.md`:
    1. `RULE-CURRENCY`: Price quoted in USD for US client or EUR for Spain (`client_country`).
    2. `RULE-SLA`: On-time delivery SLA (%) committed in proposal.
    3. `RULE-RETURNS-TIME`: No returns processing promised under 48 hours.
    4. `RULE-DISCOUNT-TIERS`: Volume discount table included.
    5. `RULE-CARRIER-RATES`: Negotiated carrier rates never revealed (only final client prices).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-Department Proposal Section Draft Generation (Priority: P1)

As a TrackFlow Commercial Account Manager,  
I want the system to take an intake-completed RFP and generate specialized proposal drafts for each active operational department (`warehouse`, `lastmile`, `reverse`),  
So that our commercial response accurately addresses client operational requirements and policy guidelines without manual document re-slicing.

**Why this priority**:
Automated section generation is the foundational capability of Part 2. It converts structured operational extracts (`key_aspects`) into cohesive business proposal text tailored to the client's country, scope, and requested services.

**Independent Test**:
Can be tested independently by providing a mock Part 1 handoff payload (e.g. for `trackflow-request-1.pdf` with `warehouse` and `reverse` active) and verifying that separated generator agents emit distinct section drafts covering storage capacity, costs, onboarding time, and return workflows without re-parsing raw PDFs.

**Acceptance Scenarios**:

1. **Given** an RFP ticket in `intake_complete` (`analisis_completo`) status with its routing handoff (`ticket_id` and synthesizer payload with `key_aspects`),  
   **When** Part 2 starts processing,  
   **Then** it consumes the routing contract directly without re-parsing the raw PDF and transitions ticket status to `drafting` (`generando_borrador`).
2. **Given** active departments scoped from Part 1 (e.g., `warehouse` and `reverse`),  
   **When** proposal generation runs,  
   **Then** each department invokes its dedicated generator agent to produce a draft section aligned with the rules, formatting, and departmental leadership outlined in `trackflow-BRIEFING.es.md`.
3. **Given** a department generator producing text,  
   **When** referencing pricing or policy parameters,  
   **Then** it formats pricing in the mandatory currency (USD for US, EUR for Spain) and incorporates known company operational standards or semantic knowledge base lookups without fabricating unconfirmed SLA figures.

---

### User Story 2 - Multi-Dimensional Parallel Evaluation & Structured EvaluationResult (Priority: P2)

As a Commercial Quality Auditor,  
I want generated department proposal sections to undergo parallel evaluations across readability, requirement relevance, and commercial compliance,  
So that flaws, policy breaches, or missing information are detected immediately with actionable feedback before customer presentation.

**Why this priority**:
Automated multi-factor evaluation guarantees high proposal quality, enforces strict business rules (such as returns turnaround limits and currency alignment), and provides structured diagnostic feedback to guide automated corrections.

**Independent Test**:
Can be tested independently by feeding a non-compliant section draft (e.g., promising 24-hour return processing or missing volume discounts) to the evaluator: the evaluator outputs a structured `EvaluationResult` with `compliance.pass == false`, specifies the exact violated rule ID and details, and generates actionable revision instructions.

**Acceptance Scenarios**:

1. **Given** a generated department proposal draft,  
   **When** evaluation runs,  
   **Then** readability (via readability metrics), relevance to RFP requirements, and compliance with briefing rules are evaluated in parallel without blocking other departments or causing database write conflicts.
2. **Given** the completion of an evaluation run for a department section,  
   **When** results are compiled,  
   **Then** a structured `EvaluationResult` is emitted containing:
   - `section_id` / `department_id`
   - `readability`: `{ pass: bool, score: float, details: str }`
   - `relevance`: `{ pass: bool, missing_aspects: string[] }`
   - `compliance`: `{ pass: bool, rule_ids: string[], violations: string[] }`
   - `overall_pass`: `bool`
   - `feedback_for_generator`: actionable, concrete revision instructions.
3. **Given** a draft section that promises return processing in 24 hours (violating the 48-hour minimum rule),  
   **When** the compliance evaluator evaluates the draft,  
   **Then** `compliance.pass` evaluates to `false`, `violations` cites rule `RULE-RETURNS-TIME`, and `overall_pass` is set to `false`.

---

### User Story 3 - Generator–Evaluator Feedback Loop & Iteration Cap (Priority: P3)

As an Operations Lead,  
I want sections that fail evaluation to be automatically revised by their respective generator using the evaluator's feedback up to a bounded iteration cap,  
So that high-quality drafts are achieved autonomously while preventing infinite loops or runaway LLM costs.

**Why this priority**:
The self-correcting feedback loop refines draft quality dynamically. The iteration cap guarantees predictable execution time and system stability by gracefully delegating stubborn issues to human review.

**Independent Test**:
Can be tested independently with a generator-evaluator test fixture configured with a 2-iteration cap: verify that after failing evaluation twice, the section transitions to `needs_human_review`, retains its latest draft and `EvaluationResult`, and leaves the ticket intact in the pipeline.

**Acceptance Scenarios**:

1. **Given** a department section draft where `overall_pass == false`,  
   **When** the iteration limit (max 3 total attempts / 2 revisions) has not been reached,  
   **Then** the section draft and structured `feedback_for_generator` are sent back to the department generator agent for revision.
2. **Given** a revised draft submitted by the generator,  
   **When** re-evaluated,  
   **Then** if all criteria pass, `overall_pass` is set to `true`, the section is marked ready for Part 3 handoff, and the feedback loop for that department terminates.
3. **Given** a department section that fails evaluation upon reaching the iteration limit,  
   **When** the iteration cap is reached,  
   **Then** the loop halts for that department, its latest draft content and structured `EvaluationResult` are retained, the section and ticket are marked `needs_human_review`, and the ticket remains in the pipeline rather than being discarded or crashed.

---

### User Story 4 - Pipeline Lifecycle State Tracking & Part 3 Handoff Packaging (Priority: P4)

As Miguel Torres (Commercial Director) and downstream approval managers,  
I want the ticket lifecycle in PostgreSQL to accurately reflect the proposal drafting and evaluation stages, and compile a complete handoff package for Part 3,  
So that the commercial team has end-to-end visibility and Part 3 can proceed with department head approvals without manual intervention.

**Why this priority**:
Maintains auditability and clean system boundary integration across the monorepo architecture, providing Part 3 with all required inputs (both passed and human-review flagged sections).

**Independent Test**:
Can be tested independently by querying PostgreSQL following completion of generation and evaluation: ticket status displays `needs_human_review` (if any section failed) or ready for handoff, with all `DepartmentSection` drafts and `EvaluationResult` objects persisted.

**Acceptance Scenarios**:

1. **Given** an RFP ticket progressing through Part 2,  
   **When** state transitions occur,  
   **Then** ticket status updates accurately across `drafting` (`generando_borrador`), `under_evaluation` (`en_evaluación`), and `needs_human_review` without prematurely setting Part 3 statuses (`esperando_aprobación` or `terminado`).
2. **Given** all active department sections have completed generation (having either passed evaluation or exhausted the iteration limit),  
   **When** Part 2 finalizes,  
   **Then** the Part 3 handoff payload is assembled containing every department's draft content, structured `EvaluationResult`, and approval readiness flag.
3. **Given** pipeline execution in `data/pipelines/`,  
   **When** persistence operations execute,  
   **Then** all state changes and evaluation artifacts persist to PostgreSQL via existing repository adapters under `services/` without adding any new external HTTP microservice.

---

### Edge Cases

- **Partial Department Failure**: What happens if `warehouse` passes evaluation on iteration 1, but `lastmile` requires 2 revisions?  
  *Handling*: Each department iterates independently; passing departments do not re-run or wait in active generation loops while other departments revise.
- **Knowledge Base Unreachability**: What happens if the semantic knowledge base or vector store is unreachable during draft generation?  
  *Handling*: Generator agents degrade gracefully by using standard briefing baseline guidelines without crashing, flagging the absence of dynamic knowledge lookups in section metadata.
- **Ambiguous or Contradictory Feedback**: How does the generator handle conflicting feedback between relevance and compliance?  
  *Handling*: Compliance rules take strict precedence; actionable revision feedback prioritizes compliance corrections before style or readability refinements.
- **Simultaneous Evaluation Completion**: Multiple department evaluators finish concurrently.  
  *Handling*: Database updates are scoped strictly to the department's section record (`ticket_id`, `department_id`), avoiding race conditions or transactional deadlocks.
- **Exhaustion of Iterations on All Departments**: What if all active departments fail compliance?  
  *Handling*: Ticket transitions to `needs_human_review` with comprehensive diagnostic violations recorded for each department, ensuring full visibility for human managers.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Part 2 pipeline MUST ingest the routing handoff payload produced by Part 1 (`ticket_id`, RFP metadata, per-department `key_aspects`, sales synthesis) directly from PostgreSQL without re-parsing raw PDF files.
- **FR-002**: Part 2 pipeline MUST preserve the Part 1 ticket status (`intake_complete` / `analisis_completo`) until generation actively commences, transitioning the ticket status to `drafting` (`generando_borrador`).
- **FR-003**: The pipeline MUST instantiate dedicated, isolated generator agents for each active department (`warehouse`, `lastmile`, `reverse`) indicated in the Part 1 handoff payload.
- **FR-004**: Department generator agents MUST format pricing, services, and operational parameters in compliance with `trackflow-BRIEFING.es.md` (e.g. currency determined by `client_country`: USD for US, EUR for Spain).
- **FR-005**: Department generator agents MAY query the existing semantic knowledge base / vector store for company policies, standard pricing tables, and tone guidelines.
- **FR-006**: The pipeline MUST execute parallel evaluation of generated department drafts across three independent dimensions:
  1. **Readability**: Scored using readability metrics (e.g. Flesch Reading Ease / Flesch-Kincaid Grade via `py-readability-metrics`).
  2. **Relevance**: Verification that all required department `key_aspects` from Part 1 are addressed without unaddressed gaps.
  3. **Compliance**: Strict rule validation against the 5 business rules defined in `trackflow-BRIEFING.es.md` (§5).
- **FR-007**: Each evaluator run MUST produce an immutable, structured `EvaluationResult` containing:
  - `section_id` / `department_id`
  - `readability`: `{ pass: bool, score: float, details: str }`
  - `relevance`: `{ pass: bool, missing_aspects: string[] }`
  - `compliance`: `{ pass: bool, rule_ids: string[], violations: string[] }`
  - `overall_pass`: `bool`
  - `feedback_for_generator`: concrete, actionable revision instructions.
- **FR-008**: The compliance evaluator MUST strictly fail (`compliance.pass = false`) any draft that violates any of the following:
  - Quoting non-matching currency (EUR for US or USD for Spain).
  - Failing to commit to an on-time delivery SLA (%).
  - Promising returns processing in less than 48 hours.
  - Omitting a volume discount tier table.
  - Disclosing negotiated internal carrier rates instead of final customer pricing.
- **FR-009**: When `overall_pass == false` and the iteration count is below the configured iteration cap, the pipeline MUST feed the draft and `feedback_for_generator` back to the corresponding department generator for revision.
- **FR-010**: The default iteration limit MUST be capped at 2 revisions (maximum 3 total attempts per department section).
- **FR-011**: When a department section reaches the iteration cap without achieving `overall_pass == true`, the revision loop for that section MUST terminate, mark the section and ticket as `needs_human_review`, and retain the latest draft and `EvaluationResult`.
- **FR-012**: The ticket MUST NOT be discarded (`descartado`) or aborted when the iteration cap is reached; it MUST remain active in the pipeline with status `needs_human_review`.
- **FR-013**: State transitions MUST accurately update the ticket lifecycle in PostgreSQL across `drafting`, `under_evaluation`, and `needs_human_review` without introducing Part 3 approval statuses (`esperando_aprobación` or `terminado`).
- **FR-014**: All generated drafts, revision histories, and `EvaluationResult` objects MUST be persistently stored in PostgreSQL via existing SQLModel repository adapters under `services/`.
- **FR-015**: When all active department sections have completed generation (passed or capped), the pipeline MUST construct a structured Part 3 handoff payload containing each department's draft content, structured `EvaluationResult`, and status flags.
- **FR-016**: The pipeline MUST be implemented within `data/pipelines/` and integrated through the existing backend under `services/` without introducing any new HTTP service or daemon process.
- **FR-017**: The test suite under `tests/pipelines/` MUST include automated unit tests covering:
  - At least one department generator agent.
  - At least one department evaluator agent (with both passing and failing test cases).
  - At least one focused compliance-failure test case verifying `compliance.pass == false` on a non-compliant fixture violating a specific briefing rule (e.g. returns turnaround < 48h).

---

### Key Entities

- **DepartmentSectionDraft**:
  - Represents the generated proposal section for an active department.
  - Attributes: `id` (UUID), `ticket_id` (UUID FK), `department_id` (`warehouse` | `lastmile` | `reverse`), `iteration` (integer, 1..3), `draft_content` (markdown/text), `status` (`drafting` | `under_evaluation` | `passed` | `needs_human_review`), `created_at` (timestamp), `updated_at` (timestamp).
- **EvaluationResult**:
  - Structured evaluation outcome for a specific section draft iteration.
  - Attributes: `id` (UUID), `section_id` (UUID FK), `department_id` (string), `iteration` (integer), `readability` (`{ pass: bool, score: float, details: str }`), `relevance` (`{ pass: bool, missing_aspects: string[] }`), `compliance` (`{ pass: bool, rule_ids: string[], violations: string[] }`), `overall_pass` (bool), `feedback_for_generator` (string), `evaluated_at` (timestamp).
- **ComplianceRuleDefinition**:
  - Standardized business compliance rules enforced by the evaluator.
  - Attributes: `rule_id` (`RULE-CURRENCY`, `RULE-SLA`, `RULE-RETURNS-TIME`, `RULE-DISCOUNT-TIERS`, `RULE-CARRIER-RATES`), `description` (string), `severity` (`CRITICAL`), `failure_message` (string).
- **ProposalGenerationHandoff (Part 3 Handoff)**:
  - Structured package passed to Part 3 human approval workflows.
  - Attributes: `ticket_id` (UUID), `rfp_metadata` (object), `department_sections` (map of department_id to `{ draft_content: str, evaluation_result: EvaluationResult, status: str, iterations: int }`), `overall_status` (`passed` | `needs_human_review`), `emitted_at` (timestamp).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Proposal draft generation for all active departments completes within 60 seconds per iteration under normal LLM response latency.
- **SC-002**: 100% of generated drafts adhere strictly to currency mapping (`USD` for US, `EUR` for ES) derived from Part 1 metadata.
- **SC-003**: 100% of compliance violations (including returns SLAs < 48 hours or omitted discount tables) are detected by the compliance evaluator with explicit rule citations.
- **SC-004**: The generator–evaluator feedback loop strictly enforces the iteration cap (≤ 3 total attempts), with zero infinite revision loops.
- **SC-005**: 100% of sections exceeding the iteration cap are flagged as `needs_human_review` with their latest draft and `EvaluationResult` preserved in PostgreSQL without ticket loss or discarding.
- **SC-006**: Department evaluations run concurrently in parallel, achieving zero thread blocking or database race conditions across independent department records.
- **SC-007**: Automated pipeline test suite in `tests/pipelines/` achieves 100% pass rate, including verified generator, evaluator pass/fail, and explicit compliance rule failure assertions.

---

## Assumptions

- **Preceding Pipeline State**: Part 1 has completed successfully, yielding a ticket in `intake_complete` (`analisis_completo`) status with valid `RFPMetadata` and department `key_aspects`.
- **Department Leadership Alignment**: In accordance with `trackflow-BRIEFING.es.md`:
  - `warehouse`: Warehouse Operations, led by Ana Whitfield (storage capacity, pallet/SKU cost, onboarding schedule).
  - `lastmile`: Last Mile & Carrier Management, led by Carlos Vega (shipping costs, destination carriers, on-time delivery SLA).
  - `reverse`: Reverse Logistics, led by Sofía Ramos (returns processing cost, turnaround time ≥ 48 hours).
- **Readability Thresholds**: Readability scores target professional business standards (e.g. Flesch Reading Ease score between 40 and 70, suitable for executive decision-makers).
- **Storage Layer**: PostgreSQL (Supabase) via SQLModel repository abstractions under `services/api/infrastructure/persistence/`, respecting Constitution Principle I and Principle II.
- **Scope Boundary**: Part 2 is strictly responsible for section generation, parallel evaluation, revision looping, and packaging the Part 3 handoff. Human approval workflows (`esperando_aprobación`), peer approval pauses, multi-department conflict arbitration, and final compiled document generation belong exclusively to Part 3.
