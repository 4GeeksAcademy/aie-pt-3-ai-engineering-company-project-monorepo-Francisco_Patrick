# Feature Specification: RFP Approval, Arbitration & Document Synthesis (Part 3 of 3)

**Feature Branch**: `feature/rfp-approval-completion`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Continuation of Spec 032-rfp-response-generation: 1. Human-in-the-Loop (HITL) & Parallel Branching (AC-1.1 Scoped Interruptions, AC-1.2 Checkpointer & Namespacing, AC-1.3 Explicit Resume & Validation, AC-1.4 Backoffice UI); 2. Guardrails, Iteration Limits & Arbitration (AC-2.1 Iteration Limit, AC-2.2 Deterministic Arbitration Node, AC-2.3 Execution Traceability); 3. Document Synthesis & Ticket Lifecycle (AC-3.1 Briefing Alignment, AC-3.2 Ticket State Transitions, AC-3.3 Automatic Final Synthesis); 4. End-to-End Verification & Testing (AC-4.1 Unit Tests in tests/pipelines/, AC-4.2 Reproducible E2E Flow)."

## Clarifications & Design Decisions

### Session 2026-11-22

- **Q1: Scoped Interruption Mechanics & Non-Blocking Parallel Execution**: How does the workflow pause a department branch for human approval without blocking other active departments?
  - **Resolution**: Approval interruptions are scoped per active department branch. In a ticket with multiple departments (e.g., `warehouse` and `reverse`), the graph halts execution solely on the branch requiring approval, maintaining state via a persistent checkpointer namespaced by ticket and department (e.g. `rfp-{ticket_id}:{department}` or `rfp-{ticket_id}`). When Ana Whitfield reviews `warehouse`, Sofía Ramos can simultaneously review or approve `reverse`. Approving one branch advances that branch's status immediately to approved without waiting for or stalling unapproved peers.
- **Q2: Deterministic Arbitration Triggers & Resolution Hierarchy**: How are cross-department conflicts evaluated and resolved without LLM voting or non-deterministic negotiations?
  - **Resolution**: Cross-department conflicts are evaluated through a dedicated deterministic arbitration node triggered exclusively by structured state conditions matching `docs/agentic-workflows/trackflow-BRIEFING.es.md`:
    1. `volume-vs-capacity`: Warehouse committed storage/throughput capacity is lower than Last Mile assumed monthly volume. Arbiter: Miguel Torres (Commercial Director). Resolution Rule: Proposal volume is capped at warehouse capacity; Last Mile must adjust volume and pricing downward.
    2. `returns-sla-breach`: Reverse logistics section (or another department embedding returns language) promises turnaround under 48 hours (breaching briefing rule 5). Arbiter: Sofía Ramos (Reverse Logistics Lead) rejects her section; if embedded in another section, Miguel Torres arbitrates. Resolution Rule: Enforce `request_changes` on any offending section; block final synthesis until compliant.
    3. `currency-mismatch`: Two sections quote different currencies, or quoted currency contradicts `client_country` (US -> USD, Spain -> EUR). Arbiter: Miguel Torres. Resolution Rule: Offending sections are rewritten in the country's canonical currency; if unresolved after max revisions, section is marked rejected.
- **Q3: Revision Iteration Limits & Escalation Path**: What happens when repeated human rejections or revision loops occur?
  - **Resolution**: An explicit verifiable iteration cap (default 2 revision cycles, max 3 submission attempts) is enforced across revision loops. If a department section fails approval or remains conflicted after reaching the cap, the loop terminates deterministically, recording an escalation record for Miguel Torres rather than creating infinite looping or orphaned ticket states.
- **Q4: Ticket Status Progression & Backward Compatibility**: How are ticket lifecycle transitions managed from Part 1 through Part 3?
  - **Resolution**: In strict alignment with `trackflow-BRIEFING.es.md` and Specs 031/032:
    - Upon entry into Part 3 with pending department reviews, ticket status transitions to `waiting_for_approval` (`esperando_aprobación`).
    - The ticket remains in `waiting_for_approval` as long as at least one active department section has not completed its approval cycle.
    - All existing row fields from Part 1 and Part 2 (PDF paths, metadata, readability scores, draft content, evaluation metrics) are fully preserved.
    - Once every active department has approved its section, the system automatically triggers final document synthesis and updates ticket status to `done` (`terminado`).
- **Q5: Backoffice UI Department Approval Workflow**: How do department leaders access and record decisions?
  - **Resolution**: The existing `uis/backoffice` proposal dashboard is extended with department-specific approval cards for Ana Whitfield (`warehouse`), Carlos Vega (`lastmile`), and Sofía Ramos (`reverse`). Approvers can inspect their department draft, evaluation findings, open questions, and submit one of three explicit validated decisions: `approve`, `reject`, or `request_changes` (with required revision feedback text).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scoped Human Approval & Parallel Branch Independence (Priority: P1)

As an operational department lead (Ana Whitfield for Warehouse, Carlos Vega for Last Mile, or Sofía Ramos for Reverse Logistics),  
I want the proposal workflow to pause at an explicit review checkpoint specifically for my department's section,  
So that I can independently verify, approve, reject, or request changes on my section without blocking or delaying other department leads who are ready to approve theirs.

**Why this priority**:
Parallel independent review is the core operational principle of Part 3. Blocking the entire workflow while waiting for a single department lead causes commercial bottlenecks, which contradicts TrackFlow's goal of delivering proposals in under 2 days.

**Independent Test**:
Can be tested independently with a multi-department ticket (e.g., `warehouse` and `lastmile` active): verify that both branches enter scoped interrupts; approving `lastmile` records Carlos Vega's approval and advances the `lastmile` branch state while `warehouse` remains paused in interrupted state, and verifying that resuming `lastmile` does not prematurely unpause or corrupt `warehouse`.

**Acceptance Scenarios**:

1. **Given** a multi-department RFP response generated in Part 2 entering the approval phase,  
   **When** execution reaches the department approval milestone,  
   **Then** the workflow triggers scoped interruptions (`interrupt`) before marking each active department section approved, pausing each department branch individually.
2. **Given** two active department branches (`warehouse` and `lastmile`) paused in scoped interruptions,  
   **When** Carlos Vega submits an approval for `lastmile` while Ana Whitfield has not yet reviewed `warehouse`,  
   **Then** the `lastmile` branch immediately records approval and advances to approved status, while the `warehouse` branch remains safely paused at its interrupt point without data loss or race conditions.
3. **Given** concurrent RFP tickets running in the system,  
   **When** state checkpoints are persisted,  
   **Then** checkpoints are partitioned by deterministic thread identifiers namespaced per ticket and department (`rfp-{ticket_id}` or `rfp-{ticket_id}:{department}`) backed by persistent storage (SQLite or PostgreSQL), ensuring concurrent tickets never share or overwrite checkpoint state.

---

### User Story 2 - Explicit Resume Entrypoint & Input Validation (Priority: P2)

As a TrackFlow backend service and API client,  
I want an explicit `resume` interface that validates human decisions and resumes the graph from the exact interrupted state,  
So that approvals, rejections, and revision requests are processed deterministically without ever restarting the workflow from scratch.

**Why this priority**:
Restarting from scratch loses prior evaluation results, inflates LLM costs, and creates duplicate tickets. Strict input validation prevents malformed decisions or unauthorized transitions from corrupting graph state.

**Independent Test**:
Can be tested independently by issuing a resume request with invalid decision payloads (e.g. missing required feedback for `request_changes` or invalid decision enum): the system rejects the call with HTTP 422; issuing a valid `approve` payload resumes from the paused node, updates `DepartmentSection.approval_status`, and preserves previous state.

**Acceptance Scenarios**:

1. **Given** an interrupted department approval branch,  
   **When** an external caller invokes the resume entry point,  
   **Then** the system validates that the human input contains a valid decision enum (`approve`, `reject`, or `request_changes`) and, if `request_changes` is chosen, validates that non-empty revision notes are provided.
2. **Given** a valid human decision submitted to resume an interrupted branch,  
   **When** the graph re-enters execution,  
   **Then** it resumes from the exact interrupted checkpoint and applies the decision without re-running upstream PDF ingestion, metadata parsing, or unrelated department nodes.
3. **Given** a department lead submits `request_changes` with structured revision feedback,  
   **When** execution resumes,  
   **Then** the graph routes the section back to the department generator with the human feedback and increments the section's revision iteration count.

---

### User Story 3 - Structured Conflict Detection & Deterministic Arbitration Node (Priority: P3)

As Miguel Torres (Commercial Director) and TrackFlow operational leadership,  
I want an explicit, deterministic arbitration node that detects structured cross-department contradictions and resolves them via predefined business rules and named arbiters,  
So that proposals never reach clients with irreconcilable operational claims, without relying on non-deterministic LLM consensus voting.

**Why this priority**:
Operational conflicts (e.g. warehouse capacity smaller than shipping volume, or impossible return SLA promises) create severe delivery liability. Deterministic arbitration guarantees strict rule adherence according to corporate policy.

**Independent Test**:
Can be tested independently by presenting a synthesized proposal state containing a deliberate conflict:
1. `volume-vs-capacity`: Warehouse max throughput is 3,000 orders/mo while Last Mile quotes 5,000 orders/mo -> Arbitration node triggers `volume-vs-capacity`, caps proposal volume at 3,000, and routes Last Mile for downward adjustment under arbiter Miguel Torres.
2. `returns-sla-breach`: Reverse section claims 24-hour turnaround -> Arbitration node triggers `returns-sla-breach`, forces `request_changes`, and records Sofía Ramos / Miguel Torres arbitration.
3. `currency-mismatch`: US client with EUR pricing -> Arbitration node triggers `currency-mismatch` and forces rewrite to USD.

**Acceptance Scenarios**:

1. **Given** generated drafts from active departments entering synthesis or inter-department review,  
   **When** the structured state contains a capacity mismatch where warehouse capacity < lastmile volume,  
   **Then** the arbitration node triggers trigger ID `volume-vs-capacity`, assigns arbiter Miguel Torres, enforces capping volume to warehouse capacity, and orders Last Mile revision.
2. **Given** any department draft promising return processing under 48 hours,  
   **When** the arbitration node evaluates the content,  
   **Then** it triggers trigger ID `returns-sla-breach`, forces a `request_changes` state on the offending section, and blocks final document synthesis until the violation is removed.
3. **Given** two active sections quoting inconsistent currencies, or a section quoting EUR for a US client,  
   **When** evaluated by the arbitration node,  
   **Then** it triggers trigger ID `currency-mismatch`, designates Miguel Torres as arbiter, and rewrites the currency to match `client_country`.
4. **Given** any revision or inter-department feedback loop,  
   **When** the loop executes,  
   **Then** an explicit iteration counter tracks cycles, and execution halts deterministically once the maximum iteration limit is reached.

---

### User Story 4 - Backoffice UI Department Approval Extension (Priority: P4)

As a department approver (Ana Whitfield, Carlos Vega, or Sofía Ramos),  
I want to log into the `uis/backoffice` proposal portal, view my department's generated section alongside key aspects and evaluation scores, and submit my approval or rejection with one click,  
So that I have a clean, intuitive interface to perform my operational review duties quickly.

**Why this priority**:
The backoffice UI provides the human touchpoint for Human-in-the-Loop governance. A dedicated UI eliminates manual email handoffs and ensures all approval timestamps and approver identities are captured directly into PostgreSQL.

**Independent Test**:
Can be tested independently by loading the backoffice proposal detail view for a ticket in `waiting_for_approval` status: the page displays scoped department approval cards showing draft text, evaluation badges, and action buttons (`Approve`, `Request Changes`, `Reject`). Submitting updates the status badge and sends the valid resume payload.

**Acceptance Scenarios**:

1. **Given** a user navigating to an RFP ticket in `uis/backoffice`,  
   **When** the ticket is in `waiting_for_approval` status,  
   **Then** the UI renders a distinct approval section for each active department displaying the department name, assigned lead, generated content, and evaluation audit status.
2. **Given** an approver viewing their department card,  
   **When** they click "Approve",  
   **Then** the UI submits a resume payload with `decision: "approve"`, updates the department status badge to "Approved", and disables further edits on that card.
3. **Given** an approver selecting "Request Changes",  
   **When** submitting,  
   **Then** the UI mandates entry of specific revision instructions in a modal or text area before sending the payload.

---

### User Story 5 - Automatic Final Document Synthesis & Ticket Lifecycle Completion (Priority: P5)

As Miguel Torres (Commercial Director) and Commercial Account Managers,  
I want the system to automatically consolidate all approved department sections into a complete, client-ready proposal document once all active departments have approved,  
So that commercial proposals are finalized immediately without manual copy-pasting, updating ticket status to `done` (`terminado`).

**Why this priority**:
Automatic synthesis ensures seamless transition from individual department sign-offs to a unified customer proposal. Enforcing that synthesis occurs **only after** all active departments have approved prevents incomplete proposals from being shared.

**Independent Test**:
Can be tested independently by setting up a ticket where department A is approved and department B is pending: verify final synthesis does not run; upon submitting approval for department B, verify final synthesis executes automatically, generates `FinalDocument` with currency and all sections, and marks ticket status `done` (`terminado`).

**Acceptance Scenarios**:

1. **Given** an RFP ticket with active departments where some but not all have approved,  
   **When** checking synthesis readiness,  
   **Then** final document synthesis remains dormant and ticket status remains `waiting_for_approval`.
2. **Given** an RFP ticket where the final pending active department records approval,  
   **When** the approval node completes,  
   **Then** the final synthesis node executes automatically, compiles all approved sections into `FinalDocument`, and binds the appropriate currency (EUR for Spain, USD for US).
3. **Given** successful compilation of `FinalDocument`,  
   **When** the pipeline concludes,  
   **Then** ticket status transitions to `done` (`terminado`), all Part 1 and Part 2 database row fields are preserved, and the final consolidated document is accessible via the API and Backoffice UI.

---

### User Story 6 - Execution Traceability & Comprehensive E2E Verification (Priority: P6)

As a TrackFlow DevOps engineer and QA auditor,  
I want every graph node execution to record its agent/node name, input, output, and timestamp in state, backed by automated unit and E2E integration test suites in `tests/pipelines/`,  
So that we have full auditability over agent decisions and can verify Parts 1, 2, and 3 end-to-end with zero regressions or state loss.

**Why this priority**:
Traceability and automated verification guarantee system reliability, facilitate post-mortem investigations of proposal errors, and prove that the entire intake-drafting-approval pipeline works deterministically.

**Independent Test**:
Can be tested independently by running `pytest tests/pipelines/` to execute unit tests for scoped interruptions, resume operations, branch independence, iteration caps, and conflict resolution, plus an automated script simulating the full Parts 1 -> 2 -> 3 flow with mock approvals.

**Acceptance Scenarios**:

1. **Given** the execution of any node in the RFP pipeline,  
   **When** the node starts and finishes execution,  
   **Then** it appends an audit record to `execution_trace` in graph state containing `node_name`, `input_summary`, `output_summary`, and ISO-8601 `timestamp`.
2. **Given** unit test suite execution under `tests/pipelines/`,  
   **When** tests run,  
   **Then** tests verify:
   - Scoped interruption and valid resume.
   - Parallel branch independence (approving Department B while Department A remains interrupted).
   - Maximum iteration limit reached and escalation handling.
   - Arbitration node triggering and deterministic resolution for `volume-vs-capacity`, `returns-sla-breach`, and `currency-mismatch`.
3. **Given** an automated end-to-end integration test/script,  
   **When** executed against sample fixtures (e.g. `trackflow-request-1.pdf` and `trackflow-request-2.pdf`),  
   **Then** it drives the ticket from upload (Part 1) to drafting/evaluation (Part 2) to simulated department approvals and final document generation (Part 3), verifying zero state jumps, zero data loss, and zero contradictory messages across part handoffs.

---

### Edge Cases

- **One Department Rejection**: What happens if Ana Whitfield rejects `warehouse` while Carlos Vega approves `lastmile`?  
  *Handling*: The `warehouse` branch transitions to `rejected` (or triggers commercial escalation with Miguel Torres), while `lastmile` retains its `approved` status. Final document synthesis is blocked; the ticket does not transition to `done` until all active departments have valid approved sections or Miguel Torres arbitrates a resolution.
- **Concurrent Approvals on Different Branches**: What happens if Ana Whitfield and Carlos Vega submit approvals at the exact same millisecond?  
  *Handling*: Each branch is namespaced by thread ID (`rfp-{ticket_id}:{department}`) and operates on its own section record in PostgreSQL. The persistent checkpointer isolates branch states, preventing race conditions or deadlock.
- **Resuming an Already Approved Branch**: What happens if a duplicate resume call is made for a branch that is already approved?  
  *Handling*: The resume endpoint checks the current branch status; if already approved or not currently interrupted, it returns a descriptive error (e.g. HTTP 409 Conflict) and does not re-execute graph nodes.
- **Missing Approver Identity**: What happens if a resume call arrives without a valid approver identifier?  
  *Handling*: The validation guard rejects the call with HTTP 422, requiring approver metadata to ensure legal and operational audit compliance.
- **Network Failure During Interrupt Checkpointing**: What happens if the database connection drops while saving an interruption checkpoint?  
  *Handling*: Transactional rollback ensures that the branch is not left in an inconsistent half-saved state; the node fails cleanly and retry logic restores the last valid checkpoint.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Human-in-the-Loop & Parallel Branching
- **FR-001**: System MUST initiate scoped graph interruptions (`interrupt`) for each active department prior to marking that department's section approved.
- **FR-002**: System MUST allow any active department branch to proceed or record approval independently without blocking or being blocked by parallel department branches.
- **FR-003**: System MUST utilize a persistent checkpointer (PostgreSQL in production/staging or SQLite in local automated tests) to store graph execution state.
- **FR-004**: System MUST namespace checkpointer `thread_id` values deterministically per ticket and department (e.g. `rfp-{ticket_id}` or `rfp-{ticket_id}:{department}`) to prevent state sharing across concurrent tickets or branches.
- **FR-005**: System MUST provide an explicit `resume` entry point that resumes graph execution directly from the interrupted node state without restarting upstream pipeline stages.
- **FR-006**: System MUST validate all incoming resume requests to ensure the decision is one of `approve`, `reject`, or `request_changes`, and that `request_changes` includes mandatory textual feedback.
- **FR-007**: Backoffice UI (`uis/backoffice`) MUST render dedicated approval review panels for each active department displaying section content, evaluation results, and action buttons for `approve`, `reject`, and `request_changes`.

#### Guardrails, Iteration Limits & Arbitration
- **FR-008**: System MUST enforce an explicit, configurable maximum iteration limit (default: 2 revisions) on any revision or inter-department feedback loop.
- **FR-009**: System MUST implement a dedicated deterministic arbitration node triggered exclusively by structured state conditions without utilizing LLM voting or unconstrained agent debate.
- **FR-010**: System MUST trigger arbitration condition `volume-vs-capacity` when warehouse capacity is insufficient for last mile order volume, resolving by capping proposal volume to warehouse capacity and directing last mile revision under arbiter Miguel Torres.
- **FR-011**: System MUST trigger arbitration condition `returns-sla-breach` when any draft promises returns turnaround under 48 hours, resolving by forcing `request_changes` under arbiter Sofía Ramos / Miguel Torres.
- **FR-012**: System MUST trigger arbitration condition `currency-mismatch` when section currencies conflict or contradict `client_country` (US -> USD, Spain -> EUR), resolving by enforcing country currency under arbiter Miguel Torres.
- **FR-013**: System MUST record structured execution traces in graph state for every node execution, logging node name, input snapshot, output snapshot, and ISO-8601 timestamp.

#### Document Synthesis & Ticket Lifecycle
- **FR-014**: System MUST strictly adhere to department leads defined in `trackflow-BRIEFING.es.md`: Ana Whitfield (`warehouse`), Carlos Vega (`lastmile`), Sofía Ramos (`reverse`), and Miguel Torres (Commercial Director).
- **FR-015**: System MUST transition ticket status to `waiting_for_approval` (`esperando_aprobación`) upon entering the human approval phase while any department approval remains pending.
- **FR-016**: System MUST maintain all database row fields and audit metadata created in Part 1 and Part 2 without data loss or truncation.
- **FR-017**: System MUST automatically invoke the final synthesis node to consolidate all approved department sections into a `FinalDocument` once and only once every active department has recorded an `approved` status.
- **FR-018**: System MUST transition ticket status to `done` (`terminado`) immediately upon successful generation and persistence of the final consolidated document.

#### Verification & Quality Assurance
- **FR-019**: System MUST provide automated unit tests in `tests/pipelines/` verifying scoped interruptions, resume validation, branch independence, iteration cap termination, and arbitration resolution for all 3 briefing conflict triggers.
- **FR-020**: System MUST provide an automated end-to-end integration test/script driving Parts 1, 2, and 3 continuously using simulated programmatic approvals and verifying complete state continuity.

---

### Key Entities *(data models)*

- **Ticket**:
  - `ticket_id`: Unique identifier (UUID).
  - `rfp_id`: Associated RFP document identifier.
  - `status`: Canonical status string (`analizando`, `descartado`, `analisis_completo`, `generando_borrador`, `en_evaluación`, `needs_human_review`, `esperando_aprobación` / `waiting_for_approval`, `terminado` / `done`).
  - `raw_pdf_path`: Filepath to uploaded PDF in persistent storage.
  - `active_departments`: List of department IDs required for this ticket (`warehouse`, `lastmile`, `reverse`).
  - `created_at`, `updated_at`: ISO-8601 timestamps.

- **DepartmentSection**:
  - `ticket_id`: Foreign key reference to Ticket.
  - `department_id`: Canonical identifier (`warehouse`, `lastmile`, `reverse`).
  - `key_aspects`: Extracted operational requirements and open questions from Part 1.
  - `draft_content`: Generated proposal markdown text from Part 2.
  - `evaluation_results`: Structured evaluation metrics (readability, relevance, compliance) from Part 2.
  - `approval_status`: Current approval state (`pending`, `approved`, `rejected`, `changes_requested`).
  - `approver`: Named responsible lead (Ana Whitfield, Carlos Vega, Sofía Ramos).
  - `review_feedback`: Optional revision feedback provided during review.
  - `iteration_count`: Integer tracking revision cycles.
  - `approved_at`: Timestamp of final approval.

- **ArbitrationLog**:
  - `ticket_id`: Foreign key reference to Ticket.
  - `trigger_id`: Canonical conflict trigger (`volume-vs-capacity`, `returns-sla-breach`, `currency-mismatch`).
  - `arbiter`: Named arbiter responsible for resolution (Miguel Torres or Sofía Ramos).
  - `rule_applied`: Description of deterministic rule enforced.
  - `resolution_details`: Structured before/after diff or action taken.
  - `created_at`: Timestamp of arbitration execution.

- **FinalDocument**:
  - `ticket_id`: Foreign key reference to Ticket.
  - `title`: Commercial proposal title.
  - `client_name`: Extracted client name.
  - `currency`: Canonical currency (`USD` or `EUR`).
  - `sections`: Consolidated map of approved department sections and executive summary.
  - `generated_at`: ISO-8601 timestamp of compilation.

- **ExecutionTraceEntry**:
  - `node_name`: Name of graph node or agent.
  - `department_id`: Optional department scope if executed on a branch.
  - `input_state`: Serialized snapshot of relevant input data.
  - `output_state`: Serialized snapshot of node outputs.
  - `timestamp`: ISO-8601 execution timestamp.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Zero Cross-Branch Blocking**: 100% of parallel department approval branches can be reviewed and approved independently without waiting for peer department actions.
- **SC-002**: **Deterministic Resume Precision**: 100% of resume calls successfully continue execution from the exact interrupted state without re-running prior pipeline nodes.
- **SC-003**: **Strict Arbitration Determinism**: 100% of structured conflict triggers (`volume-vs-capacity`, `returns-sla-breach`, `currency-mismatch`) resolve via designated briefing rules without invoking unconstrained LLM voting.
- **SC-004**: **Bounded Execution Guarantee**: 0% of revision loops exceed the configured iteration cap (max 2 revisions / 3 total attempts), terminating with escalation if unresolved.
- **SC-005**: **End-to-End Proposal Turnaround**: End-to-end automated pipeline runtime (excluding human pause time) finishes in under 60 seconds from PDF upload to final consolidated document generation.
- **SC-006**: **Zero State Regressions**: 100% of data fields captured in Parts 1 and 2 persist intact through Part 3 completion with zero data loss or state skips.
- **SC-007**: **Automated Test Coverage**: 100% of unit test scenarios (interrupt, resume, branch independence, iteration cap, arbitration triggers) and E2E handoff flows pass consistently in CI/test environments.

---

## Assumptions

- **Persistent Checkpointer**: Local test environments utilize SQLite checkpointers (`SqliteSaver`), while staging/production deployments utilize PostgreSQL checkpointers (`PostgresSaver`) to guarantee state durability across server restarts.
- **Briefing Authority**: The organizational structure and policy rules defined in `docs/agentic-workflows/trackflow-BRIEFING.es.md` are the single source of truth; no additional management tiers or approval hierarchies exist at TrackFlow.
- **Backoffice UI Framework**: The approval interface builds upon the existing Next.js App Router application in `uis/backoffice` using standard REST API endpoints exposed by `services/api/`.
- **Stateless Agent Execution**: Graph nodes remain stateless; all state is passed via the LangGraph state schema and persisted through the checkpointer and database repository adapters.
