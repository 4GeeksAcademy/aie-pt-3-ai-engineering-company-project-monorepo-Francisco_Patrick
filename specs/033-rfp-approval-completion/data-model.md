# Domain Data Model & State Machine: RFP Approval, Arbitration & Document Synthesis (Part 3 of 3)

**Branch**: `033-rfp-approval-completion` | **Date**: 2026-11-22 | **Spec**: [specs/033-rfp-approval-completion/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/033-rfp-approval-completion/spec.md)

---

## 1. Domain Entities & Relationships

```mermaid
erDiagram
    TICKET ||--o{ DEPARTMENT_SECTION : "has active sections"
    TICKET ||--o{ ARBITRATION_LOG : "records conflicts"
    TICKET ||--o| FINAL_DOCUMENT : "consolidates into"
    TICKET ||--o{ EXECUTION_TRACE : "tracks node executions"

    TICKET {
        uuid ticket_id PK
        string ticket_number
        string status
        string raw_pdf_path
        string[] active_departments
        datetime created_at
        datetime updated_at
    }

    DEPARTMENT_SECTION {
        uuid id PK
        uuid ticket_id FK
        string department_id
        string department_name
        string responsible_person
        json key_aspects
        text draft_content
        json evaluation_results
        string approval_status
        string approver
        text review_feedback
        int iteration_count
        datetime approved_at
    }

    ARBITRATION_LOG {
        uuid id PK
        uuid ticket_id FK
        string trigger_id
        string arbiter
        string rule_applied
        json resolution_details
        datetime created_at
    }

    FINAL_DOCUMENT {
        uuid id PK
        uuid ticket_id FK
        string title
        string client_name
        string currency
        text executive_summary
        json sections
        datetime generated_at
    }

    EXECUTION_TRACE {
        uuid id PK
        uuid ticket_id FK
        string node_name
        string department_id
        json input_state
        json output_state
        datetime timestamp
    }
```

---

## 2. Entity Specifications & Field Constraints

### 2.1 Ticket (`IntakeTicket`)
Represents the top-level RFP intake and commercial proposal lifecycle.

| Field | Type | Nullable | Description / Constraints |
|---|---|---|---|
| `ticket_id` | `UUID` | No | Primary Key. |
| `ticket_number` | `str` | No | Unique human-readable ticket reference (e.g. `RFP-2026-001`). |
| `status` | `TicketStatus` | No | Lifecycle status: `analizando`, `descartado`, `analisis_completo`, `generando_borrador`, `en_evaluación`, `needs_human_review`, `esperando_aprobación`, `terminado`. |
| `raw_pdf_path` | `str` | No | Path to uploaded PDF in storage (`data/raw/`). |
| `active_departments`| `List[str]` | No | List of required departments (`warehouse`, `lastmile`, `reverse`). |
| `created_at` | `datetime` | No | UTC timestamp when created. |
| `updated_at` | `datetime` | No | UTC timestamp when last updated. |

### 2.2 DepartmentSection (`DepartmentSectionTable`)
Captures department-specific proposal text, operational parameters, and human review status.

| Field | Type | Nullable | Description / Constraints |
|---|---|---|---|
| `id` | `UUID` | No | Primary Key. |
| `ticket_id` | `UUID` | No | Foreign Key referencing `Ticket.ticket_id`. |
| `department_id` | `str` | No | One of `warehouse`, `lastmile`, `reverse`. |
| `department_name` | `str` | No | Display name (e.g. "Warehouse Operations"). |
| `responsible_person`| `str` | No | Named lead: `Ana Whitfield`, `Carlos Vega`, `Sofía Ramos`. |
| `key_aspects` | `Dict[str, Any]` | No | JSON structured operational parameters from Part 1. |
| `draft_content` | `str` | Yes | Markdown section content generated in Part 2 or revised in Part 3. |
| `evaluation_results`| `Dict[str, Any]` | Yes | Structured readability, relevance, and compliance scores. |
| `approval_status` | `str` | No | `pending`, `approved`, `rejected`, `changes_requested`. |
| `approver` | `str` | Yes | Name of human approver recording the decision. |
| `review_feedback` | `str` | Yes | Required revision instructions if `changes_requested`. |
| `iteration_count` | `int` | No | Revision loop counter (0..2 revisions, max 3 attempts). Default: `0`. |
| `approved_at` | `datetime` | Yes | UTC timestamp when approval was granted. |

### 2.3 ArbitrationLog (`ArbitrationLogTable`)
Audit log recording every deterministic conflict detected and resolved by the arbitration node.

| Field | Type | Nullable | Description / Constraints |
|---|---|---|---|
| `id` | `UUID` | No | Primary Key. |
| `ticket_id` | `UUID` | No | Foreign Key referencing `Ticket.ticket_id`. |
| `trigger_id` | `str` | No | One of `volume-vs-capacity`, `returns-sla-breach`, `currency-mismatch`. |
| `arbiter` | `str` | No | Named arbiter: `Miguel Torres` (Commercial Director) or `Sofía Ramos` (Reverse Logistics Lead). |
| `rule_applied` | `str` | No | Description of deterministic business rule enforced. |
| `resolution_details`| `Dict[str, Any]`| No | Before/after state snapshot and corrective actions taken. |
| `created_at` | `datetime` | No | UTC timestamp of arbitration execution. |

### 2.4 FinalDocument (`FinalDocumentTable`)
Consolidated, client-ready commercial proposal generated automatically upon 100% department approval.

| Field | Type | Nullable | Description / Constraints |
|---|---|---|---|
| `id` | `UUID` | No | Primary Key. |
| `ticket_id` | `UUID` | No | Foreign Key referencing `Ticket.ticket_id` (Unique). |
| `title` | `str` | No | Commercial proposal title (e.g. "Propuesta Logística Integral - ModaViva"). |
| `client_name` | `str` | No | Name of prospective client. |
| `currency` | `str` | No | Operating currency: `EUR` (Spain) or `USD` (United States). |
| `executive_summary` | `str` | No | High-level synthesis tailored for client executive leadership. |
| `sections` | `Dict[str, Any]` | No | JSON map of approved department sections and operational commitments. |
| `generated_at` | `datetime` | No | UTC timestamp of document compilation. |

### 2.5 ExecutionTraceEntry (Graph State Trace)
In-memory audit entry recorded by each LangGraph node for execution traceability.

| Field | Type | Nullable | Description / Constraints |
|---|---|---|---|
| `node_name` | `str` | No | Canonical graph node name (e.g. `arbitration_node`, `approval_node`). |
| `department_id` | `str` | Yes | Department scope if node is on a parallel branch. |
| `input_state` | `Dict[str, Any]` | No | Serialized summary of input state. |
| `output_state` | `Dict[str, Any]` | No | Serialized summary of node outputs. |
| `timestamp` | `datetime` | No | UTC execution timestamp. |

---

## 3. State Machine & Transitions

### 3.1 Ticket Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> analizando: Upload PDF (Part 1)
    analizando --> descartado: Invalid / Not RFP
    analizando --> analisis_completo: Part 1 Complete
    analisis_completo --> generando_borrador: Initiate Part 2
    generando_borrador --> en_evaluación: Generator Complete
    en_evaluación --> needs_human_review: Evaluation Capped (3 attempts)
    en_evaluación --> esperando_aprobación: Evaluation Passed
    needs_human_review --> esperando_aprobación: Review Accepted / Manual Sign-off
    
    state esperando_aprobación {
        [*] --> BranchEvaluation
        BranchEvaluation --> ScopedInterrupts: Parallel Fan-Out
        ScopedInterrupts --> DepartmentApproved: Human Decision = approve
        ScopedInterrupts --> DepartmentRevision: Human Decision = request_changes
        ScopedInterrupts --> DepartmentRejected: Human Decision = reject
        DepartmentRevision --> ScopedInterrupts: Regenerate & Re-evaluate (iter < 2)
        DepartmentRevision --> EscalatedToCommercial: Iteration Cap Reached (>= 2)
    }

    esperando_aprobación --> ArbitrationTriggered: Contradiction Detected
    ArbitrationTriggered --> esperando_aprobación: Rule Enforced & Sections Updated
    
    esperando_aprobación --> terminado: 100% Active Departments Approved
    terminado --> [*]
```

### 3.2 Department Branch Approval State Transitions

```mermaid
stateDiagram-v2
    [*] --> pending: Initial Entry into Part 3
    pending --> interrupted: Scoped interrupt() reached
    interrupted --> approved: Resume with decision='approve'
    interrupted --> changes_requested: Resume with decision='request_changes'
    interrupted --> rejected: Resume with decision='reject'
    
    changes_requested --> pending: Generator re-drafts (iteration + 1)
    changes_requested --> escalated: iteration_count >= 2 (escalated to Miguel Torres)
    
    approved --> [*]
    rejected --> [*]
    escalated --> [*]
```

---

## 4. Conflict Arbitration Rules Matrix

| Trigger ID | Trigger Condition | Arbiter | Action / Resolution Rule | Post-Resolution Edge |
|---|---|---|---|---|
| `volume-vs-capacity` | `metadata.monthly_volume > warehouse_capacity` | **Miguel Torres** | Cap proposal volume at warehouse capacity; force `lastmile` section to adjust volume and pricing downward. | Route `lastmile` to re-drafting. |
| `returns-sla-breach` | Section draft promises return turnaround $< 48$ hours | **Sofía Ramos** (or **Miguel Torres** if in non-reverse section) | Enforce `request_changes` on offending section; rewrite SLA $\ge 48$ hours. Block synthesis until compliant. | Route offending section to revision. |
| `currency-mismatch` | Inconsistent currencies across sections, or currency $\ne$ country canonical currency (`ES` $\rightarrow$ `EUR`, `US` $\rightarrow$ `USD`) | **Miguel Torres** | Rewrite currency symbols and price figures to match country currency. | Route section to revision or auto-fix. |
