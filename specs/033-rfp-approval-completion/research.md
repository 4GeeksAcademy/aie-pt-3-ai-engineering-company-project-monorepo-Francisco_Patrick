# Research & Architectural Decisions: RFP Approval, Arbitration & Document Synthesis (Part 3 of 3)

**Branch**: `033-rfp-approval-completion` | **Date**: 2026-11-22 | **Spec**: [specs/033-rfp-approval-completion/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/033-rfp-approval-completion/spec.md)

---

## 1. Technical Context Summary

- **Language/Runtime**: Python 3.14 (Backend services in `services/api/`, pipelines in `data/pipelines/`), TypeScript 5.8 (Frontends in `uis/backoffice/`, shared contracts in `packages/shared/`)
- **Primary Frameworks**: FastAPI (0.141+), SQLModel / SQLAlchemy 2.0, LangGraph (1.2+), Pydantic v2 (2.13+), Next.js 14+ App Router, Tailwind CSS
- **Persistence & Checkpointing**: PostgreSQL (Supabase) via SQLModel repository abstractions; LangGraph state checkpointers via `SqliteSaver` (local dev & automated unit/integration tests) and `PostgresSaver` (staging/production environments)
- **Testing**: `pytest` for backend unit/integration tests (`tests/pipelines/`, `services/api/tests/`), Jest / React Testing Library for frontend component tests (`uis/backoffice/__tests__/`)

---

## 2. Research Tasks & Architectural Decisions

### Research Task 1: Human-in-the-Loop (HITL) Interruption Mechanics & State Checkpointing

- **Problem / Context**:
  How does the agentic workflow pause a department approval branch to wait for human operational review (Ana Whitfield, Carlos Vega, Sofía Ramos) without busy-waiting, polling in loops, or losing state, while supporting clean resumption?
- **Decision**:
  Adopt native LangGraph `interrupt()` in combination with a persistent checkpointer (`SqliteSaver` in test suites, `PostgresSaver` in production). When a department branch reaches the review checkpoint, the node invokes `interrupt({"department_id": dept_id, "ticket_id": str(ticket_id), "action": "approval_required", "draft_content": ...})`. The graph suspends execution and persists state snapshots. External resume requests invoke the graph via `graph.invoke(Command(resume=decision_payload), config={"configurable": {"thread_id": thread_id}})`.
- **Rationale**:
  - `interrupt()` suspends execution deterministically without blocking Python threads or event loops.
  - Checkpointers persist state history and node boundaries across process restarts and horizontal scaling.
  - `Command(resume=...)` allows clean injection of human decisions (`approve`, `reject`, `request_changes`) directly back into the paused node.
- **Alternatives Considered**:
  - *Custom database polling / sleep loops*: Discarded because polling wastes compute, blocks workers, and creates synchronization bottlenecks.
  - *Webhook callbacks without checkpointers*: Discarded because recovering prior memory and graph variables after restarts would require ad-hoc serialization and complex rehydration logic.

---

### Research Task 2: Parallel Branch Independence & Namespaced Checkpointers

- **Problem / Context**:
  In a multi-department RFP (e.g., `warehouse` and `reverse`), how do we ensure that Carlos Vega or Sofía Ramos can review and approve their section without blocking or waiting for Ana Whitfield, avoiding cross-branch deadlocks or state overwrites?
- **Decision**:
  Implement thread partitioning and scoped fan-out:
  1. LangGraph supports fan-out branches where each branch executes an independent department node pipeline.
  2. The checkpointer utilizes deterministic thread identifiers: `rfp-{ticket_id}` as the parent ticket thread, with branch checkpoints scoped or sub-thread namespaced per department (`rfp-{ticket_id}:{department_id}`) when running isolated department subgraphs, or leveraging LangGraph 1.2+ multi-task branch interruption isolation.
  3. When an interrupt is triggered on branch A (`warehouse`), branch B (`reverse`) continues execution to its own interrupt or completion independently.
  4. Approving branch B immediately updates `DepartmentSection.approval_status = "approved"` in PostgreSQL and advances branch B's state, leaving branch A safely suspended.
- **Rationale**:
  - Preserves TrackFlow's core operational SLA of delivering proposals in under 2 days by eliminating inter-department review serial bottlenecks.
  - Prevents race conditions and lock contention in PostgreSQL by isolating department section updates to distinct rows.
- **Alternatives Considered**:
  - *Strictly sequential approvals*: Ana must approve before Carlos can review. Discarded as an unacceptable commercial bottleneck that directly breaches AC-1.1 and BRIEFING §6.
  - *Single monolithic interrupt for all departments*: Discarded because an approver could not submit their decision without forcing other leads to submit simultaneously.

---

### Research Task 3: Deterministic Arbitration Node & Conflict Resolution Hierarchy

- **Problem / Context**:
  How should cross-department contradictions be evaluated and resolved without stochastic LLM debate or unconstrained agent voting?
- **Decision**:
  Implement an explicit, deterministic Python arbitration node (`ArbitrationNode`) triggered strictly by structured state conditions matching `docs/agentic-workflows/trackflow-BRIEFING.es.md` §7:
  1. `volume-vs-capacity`:
     - *Condition*: `metadata.monthly_volume > warehouse_capacity` (e.g., warehouse committed capacity < lastmile assumed monthly volume).
     - *Fixed Arbiter*: Miguel Torres (Commercial Director).
     - *Resolution Rule*: Cap proposed volume at warehouse capacity; force `lastmile` section to adjust volume and pricing downward.
  2. `returns-sla-breach`:
     - *Condition*: Any section draft contains promised returns processing turnaround under 48 hours (e.g. 24h, same-day).
     - *Fixed Arbiter*: Sofía Ramos (Reverse Logistics Lead) rejects her section; if another department embeds the claim, Miguel Torres arbitrates.
     - *Resolution Rule*: Force `request_changes` on any offending section; block final document synthesis until compliant.
  3. `currency-mismatch`:
     - *Condition*: Multiple sections quote different currencies, or quoted currency contradicts `client_country` (US -> USD, Spain -> EUR).
     - *Fixed Arbiter*: Miguel Torres.
     - *Resolution Rule*: Rewrite offending sections into canonical country currency; if unresolved after max revisions, mark section rejected.
  4. *Audit Logging*: Every triggered arbitration appends an immutable entry to `ArbitrationLogTable` in PostgreSQL and `arbitration_logs` in graph state.
- **Rationale**:
  - Guarantees 100% deterministic compliance with TrackFlow corporate governance and legal policy.
  - Eliminates prompt drift, hallucinated compromises, and non-deterministic agent arguments.
- **Alternatives Considered**:
  - *LLM Judge / Consensus voting*: Discarded because LLM negotiation can violate rigid corporate policies (e.g. agreeing to 24h returns turnaround under perceived customer urgency).
  - *Hard crash / exception throwing*: Discarded because operational conflicts are normal in RFP synthesis and must be resolved gracefully through named arbiters.

---

### Research Task 4: Revision Iteration Limits & Escalation Handling

- **Problem / Context**:
  How to prevent endless feedback loops when department leads repeatedly request changes or arbitration triggers revisions?
- **Decision**:
  Enforce a hard iteration cap:
  - Default `max_iterations = 2` revision cycles (3 total submission attempts).
  - Each department section tracks `iteration_count`.
  - When an approver submits `request_changes` or arbitration forces a rewrite:
    - If `iteration_count < max_iterations`: route back to generator agent with revision notes, incrementing `iteration_count`.
    - If `iteration_count >= max_iterations`: transition section to `escalated` / `needs_human_review`, notify Miguel Torres (Commercial Director), and halt automated looping.
- **Rationale**:
  - Prevents infinite loops and bounded compute/API costs.
  - Ensures human commercial leadership retains ultimate discretion on edge-case proposals.
- **Alternatives Considered**:
  - *Discard ticket after max attempts*: Discarded because commercial leads should decide whether to proceed with manual terms rather than losing prospective enterprise clients.

---

### Research Task 5: Document Synthesis & Ticket Lifecycle Transitions

- **Problem / Context**:
  When and how should final document compilation occur, and how do ticket statuses transition throughout Part 3?
- **Decision**:
  1. *Lifecycle Transitions*:
     - Entry into Part 3: `TicketStatus.WAITING_FOR_APPROVAL` (`esperando_aprobación`).
     - The ticket remains in `waiting_for_approval` as long as any active department section has `approval_status != "approved"`.
     - Once **all** active department sections reach `approval_status == "approved"`, the workflow triggers `FinalSynthesisNode`.
     - Upon successful synthesis and persistence, ticket transitions to `TicketStatus.TERMINADO` (`done` / `terminado`).
  2. *Synthesis Content*:
     - `FinalDocument`: Includes document title, client profile, canonical currency, executive summary, and consolidated markdown sections from each approved department.
     - Preserves all Part 1 and Part 2 fields (raw PDF path, metadata, readability metrics, evaluation history).
- **Rationale**:
  - Strict gate: proposals cannot be delivered to clients with unapproved or rejected sections.
  - Conforms to BRIEFING §2.3 and §6.
- **Alternatives Considered**:
  - *Partial document delivery*: Discarded because sending a proposal with missing logistics sections breaches professional standards.

---

### Research Task 6: Backoffice UI Integration for Department Approvers

- **Problem / Context**:
  How should department leads interact with the approval system in `uis/backoffice`?
- **Decision**:
  Extend `uis/backoffice/app/rfp/[id]/page.tsx` with a dedicated `DepartmentApprovalPanel` component:
  1. Renders cards for each active department with responsible lead badge:
     - Ana Whitfield (`warehouse`)
     - Carlos Vega (`lastmile`)
     - Sofía Ramos (`reverse`)
  2. Displays section markdown draft, key aspects, and latest evaluation findings.
  3. Action controls:
     - `Approve`: Submits resume payload `{"decision": "approve", "approver": "Ana Whitfield"}`.
     - `Request Changes`: Opens revision feedback text area; validates non-empty input before sending `{"decision": "request_changes", "approver": "...", "feedback": "..."}`.
     - `Reject`: Submits `{"decision": "reject", "approver": "...", "feedback": "..."}`.
  4. Real-time feedback: updates section status badge and disables buttons once submitted.
- **Rationale**:
  - Simple, intuitive UI aligning with TrackFlow operational leads.
  - Strictly typed TypeScript components conforming to workspace strict rules.
- **Alternatives Considered**:
  - *Email approval links with magic tokens*: Discarded for initial scope; Backoffice UI provides centralized authenticated management.
