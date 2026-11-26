# Data Model: NIST Security Practices & AI Governance Baseline

**Feature Branch**: `037-nist-security-practices`  
**Specification**: [specs/037-nist-security-practices/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/037-nist-security-practices/spec.md)  
**Date**: 2026-11-25  

---

## 1. Entity Relationship Overview

The data model for NIST Security Practices and AI Governance establishes structured domain entities for asset governance, third-party vendor accountability, security-by-design execution gates, human-in-the-loop operational reviews, and regulatory risk tracking.

```mermaid
erDiagram
    AISystemRecord ||--o{ SecurityAuditLogEntry : "generates"
    AISystemRecord ||--o| SharedResponsibilityRecord : "governed_by"
    AISystemRecord ||--o{ HITLApprovalRequest : "proposes"
    HITLApprovalRequest ||--|| SecurityAuditLogEntry : "produces_audit"
    NISTFunctionAssessment ||--|{ NISTControlAction : "contains"
    NISTFunctionAssessment ||--o{ ResidualRiskRecord : "tracks_gaps"
    PromptBoundaryFilter ||--o{ SecurityAuditLogEntry : "intercepts"
    OutputValidationGate ||--o{ SecurityAuditLogEntry : "verifies"
```

---

## 2. Domain Entities & Schema Definitions

### 2.1 AISystemRecord

Represents an inventoried AI subsystem operating within the TrackFlow monorepo, identifying custodians, architectural scope, input attack surfaces, and sensitive data tier.

```mermaid
classDiagram
    class AISystemRecord {
        +string system_id
        +string name
        +string description
        +string repository_path
        +AISystemArchitecture architecture_type
        +string custodian_team
        +string technical_lead
        +DataClassification data_classification
        +List~string~ input_attack_surfaces
        +boolean requires_hitl_gates
        +boolean rate_limiting_enabled
        +datetime last_audited_at
    }

    class AISystemArchitecture {
        <<enumeration>>
        AUTONOMOUS_AGENT
        DECISION_ENGINE
        RAG_PIPELINE
        MCP_SERVER_TOOL
    }

    class DataClassification {
        <<enumeration>>
        RESTRICTED_PII
        CONFIDENTIAL_B2B
        INTERNAL_OPERATIONAL
        PUBLIC_TRANSIT
    }

    AISystemRecord --> AISystemArchitecture
    AISystemRecord --> DataClassification
```

#### Field Specifications:
- `system_id` (string, required): Canonical identifier (e.g. `TF-AI-01-CX-AGENT`, `TF-AI-02-CARRIER-ENGINE`).
- `name` (string, required): Human-readable service name.
- `description` (string, required): Operational mandate and responsibility.
- `repository_path` (string, required): Relative path to implementation root.
- `architecture_type` (AISystemArchitecture, required): Categorization of AI design pattern.
- `custodian_team` (string, required): Department owning runtime maintenance.
- `technical_lead` (string, required): Designated engineer accountable for compliance.
- `data_classification` (DataClassification, required): Highest classification of processed data.
- `input_attack_surfaces` (List[string], required): Identified untrusted input vectors.
- `requires_hitl_gates` (boolean, required): Whether system interacts with irreversible actions.
- `rate_limiting_enabled` (boolean, required): Whether endpoint rate limiting is active.
- `last_audited_at` (datetime, required): UTC timestamp of latest governance audit.

---

### 2.2 SharedResponsibilityRecord

Delineates the security and compliance contract boundary between TrackFlow and external third-party model and infrastructure providers.

```mermaid
classDiagram
    class SharedResponsibilityRecord {
        +string provider_id
        +string provider_name
        +VendorCategory vendor_category
        +string service_scope
        +List~string~ trackflow_responsibilities
        +List~string~ vendor_responsibilities
        +DataRetentionPolicy data_retention_agreement
        +boolean zero_data_retention_active
        +boolean transit_encryption_enforced
        +string governing_dpa_reference
    }

    class VendorCategory {
        <<enumeration>>
        FOUNDATION_MODEL_API
        VECTOR_DATABASE_CLOUD
        COURIER_CARRIER_INTEGRATION
    }

    class DataRetentionPolicy {
        <<enumeration>>
        ZERO_RETENTION_EPHEMERAL
        PERSISTENT_ENCRYPTED_30_DAYS
        TENANT_ISOLATED_INDEX
    }

    SharedResponsibilityRecord --> VendorCategory
    SharedResponsibilityRecord --> DataRetentionPolicy
```

#### Field Specifications:
- `provider_id` (string, required): Unique identifier (e.g. `VEND-ANTHROPIC`, `VEND-QDRANT`, `VEND-UPS`).
- `provider_name` (string, required): Legal company entity.
- `vendor_category` (VendorCategory, required): Type of outsourced service.
- `service_scope` (string, required): Exact operational interface used by TrackFlow.
- `trackflow_responsibilities` (List[string], required): Mandatory controls enforced by TrackFlow.
- `vendor_responsibilities` (List[string], required): Controls guaranteed by provider contract/SLA.
- `zero_data_retention_active` (boolean, required): Confirms customer data is not retained for training.
- `transit_encryption_enforced` (boolean, required): Confirms TLS 1.3 in transit.
- `governing_dpa_reference` (string, required): Legal Data Processing Agreement document ID.

---

### 2.3 HITLApprovalRequest

Represents an irreversible or high-impact operational action intercepted by security policy gates awaiting human supervisor authorization.

```mermaid
stateDiagram-v2
    [*] --> PENDING_HUMAN_APPROVAL: Action Intercepted by Policy Gate
    PENDING_HUMAN_APPROVAL --> HUMAN_APPROVED: Supervisor Authorizes
    PENDING_HUMAN_APPROVAL --> HUMAN_REJECTED: Supervisor Rejects
    PENDING_HUMAN_APPROVAL --> EXPIRED_FAIL_SECURE: Review Window Exceeded (Timeout)
    HUMAN_APPROVED --> EXECUTED: Adapter Invoked
    HUMAN_REJECTED --> [*]: Halted & Logged
    EXPIRED_FAIL_SECURE --> [*]: Cancelled Securely
    EXECUTED --> [*]
```

#### Field Specifications:
- `request_id` (string, required): UUID identifier of approval request.
- `action_type` (string, required): One of the 4 irreversible actions:
  - `RETURN_APPROVAL` (High-value return > threshold EUR)
  - `HIGH_VALUE_DISPATCH` (Unverified parcel dispatch > threshold EUR)
  - `CARRIER_REASSIGNMENT` (In-transit parcel carrier change)
  - `CROSS_BRAND_METRIC_SHARE` (Cross-tenant brand metric query)
- `entity_id` (string, required): Target entity identifier (Order ID, Parcel ID, Brand ID).
- `requested_by_session` (string, required): Originating agent conversation/session identifier.
- `requested_by_agent` (string, required): Name/ID of proposing AI component.
- `payload_snapshot` (Dict[str, Any], required): Complete parameters of proposed action.
- `monetary_impact_eur` (float, optional): Financial amount involved.
- `status` (ApprovalStatus, required): `PENDING_HUMAN_APPROVAL`, `HUMAN_APPROVED`, `HUMAN_REJECTED`, `EXPIRED_FAIL_SECURE`.
- `reviewer_id` (string, optional): ID of supervisor resolving request.
- `decision_notes` (string, optional): Justification provided by reviewer.
- `created_at` (datetime, required): Interception timestamp in UTC.
- `expires_at` (datetime, required): Expiration deadline before failing secure.
- `resolved_at` (datetime, optional): Resolution timestamp in UTC.

---

### 2.4 SecurityAuditLogEntry

Structured, tamper-evident audit record capturing agent decisions, security guardrail interceptions, and supervisor actions.

#### Field Specifications:
- `event_id` (string, required): Unique cryptographic audit event identifier.
- `timestamp` (datetime, required): UTC ISO-8601 creation timestamp.
- `agent_id` (string, required): Identifier of agent emitting the event.
- `session_id` (string, required): Authenticated session identifier.
- `tenant_id` (string, required): B2B brand ID or B2C customer ID partition.
- `event_category` (AuditCategory, required): `PROMPT_BOUNDARY_CHECK`, `OUTPUT_VALIDATION`, `RATE_LIMIT_CHECK`, `HITL_GATE_TRIGGER`, `SUPERVISOR_RESOLUTION`.
- `action_attempted` (string, required): Operation or tool name.
- `input_parameters_redacted` (Dict[str, Any], required): Sanitized inputs with PII/tokens masked.
- `policy_rules_evaluated` (List[string], required): Business and security rules checked.
- `decision_outcome` (string, required): `ALLOWED`, `BLOCKED`, `PENDING_REVIEW`, `INTERCEPTED`.
- `reasoning_rationale` (string, required): Transparent explanation of decision.
- `client_ip` (string, optional): Hashed or masked client IP.

---

### 2.5 ResidualRiskRecord

Tracks identified security gaps, architectural limitations, or deferred mitigations with business impact assessments and remediation roadmaps.

```mermaid
classDiagram
    class ResidualRiskRecord {
        +string risk_id
        +NISTFunctionCategory nist_function
        +string description
        +RiskSeverity severity
        +string business_impact
        +List~string~ compensatory_controls
        +string target_remediation_milestone
        +string risk_owner
        +RiskStatus status
    }

    class NISTFunctionCategory {
        <<enumeration>>
        GOVERN
        IDENTIFY
        PROTECT
        DETECT
        RESPOND
        RECOVER
    }

    class RiskSeverity {
        <<enumeration>>
        CRITICAL
        HIGH
        MEDIUM
        LOW
    }

    class RiskStatus {
        <<enumeration>>
        ACCEPTED_TEMPORARY
        REMEDIATION_SCHEDULED
        REMEDIATED
    }

    ResidualRiskRecord --> NISTFunctionCategory
    ResidualRiskRecord --> RiskSeverity
    ResidualRiskRecord --> RiskStatus
```

#### Field Specifications:
- `risk_id` (string, required): Canonical risk identifier (e.g. `RISK-NIST-PR-01`).
- `nist_function` (NISTFunctionCategory, required): Associated NIST CSF 2.0 function.
- `description` (string, required): Detailed summary of technical limitation.
- `severity` (RiskSeverity, required): Impact rating (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- `business_impact` (string, required): Operational, legal, or financial consequence if exploited.
- `compensatory_controls` (List[string], required): Active intermediate safeguards.
- `target_remediation_milestone` (string, required): Planned release or quarter for permanent fix.
- `risk_owner` (string, required): Designated engineering lead.
- `status` (RiskStatus, required): Active lifecycle state.

---

### 2.6 NIST CSF 2.0 Assessment & Control Action

```mermaid
classDiagram
    class NISTAssessmentFunction {
        +NISTFunctionCategory function
        +string function_name
        +string overview
        +List~NISTControlAction~ control_actions
        +ComplianceRating compliance_rating
    }

    class NISTControlAction {
        +string control_id
        +string category_code
        +string title
        +string concrete_operational_action
        +string verification_mechanism
        +string implementation_location
        +string priority
    }

    class ComplianceRating {
        <<enumeration>>
        COMPLIANT_VERIFIED
        PARTIALLY_IMPLEMENTED
        PLANNED
    }

    NISTAssessmentFunction --> NISTControlAction
    NISTAssessmentFunction --> ComplianceRating
```

---

## 3. Security-by-Design Execution Flow

The following sequence details how untrusted customer or external inputs flow through the prompt boundary delimiter, rate limiter, execution engine, and output validation allowlist.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Customer / Webhook
    participant RateLimiter as Rate Limit Filter
    participant BoundaryFilter as Prompt Boundary Delimiter
    participant AgentEngine as Agent / Decision Engine
    participant HITLGate as HITL Authorization Gate
    participant OutputValidator as Output Allowlist Validator
    participant Adapter as External Tool / Courier Adapter
    participant AuditLog as Security Audit Logger

    Client->>RateLimiter: POST /api/v1/agent/query
    alt Rate limit exceeded (> 30 req/min)
        RateLimiter-->>Client: HTTP 429 Too Many Requests
        RateLimiter->>AuditLog: Log RATE_LIMIT_EXCEEDED
    else Within quota
        RateLimiter->>BoundaryFilter: Forward payload
        BoundaryFilter->>BoundaryFilter: Sanitize & envelop in <<<EXTERNAL_UNTRUSTED_CONTENT>>>
        BoundaryFilter->>AgentEngine: Pass bounded context
        AgentEngine->>AgentEngine: Formulate proposed action/tool call
        
        alt Action is Irreversible (e.g. Return > 100 EUR, In-Transit Carrier Change)
            AgentEngine->>HITLGate: Evaluate action policy
            HITLGate->>AuditLog: Create HITLApprovalRequest (PENDING)
            HITLGate-->>Client: Action queued for Human Supervisor Review
        else Standard Action
            AgentEngine->>OutputValidator: Propose tool execution
            alt Malformed or unapproved tool/query
                OutputValidator->>AuditLog: Log GUARDRAIL_VIOLATION
                OutputValidator-->>Client: Refuse action safely
            else Schema matches allowlist
                OutputValidator->>Adapter: Execute verified adapter
                Adapter-->>AgentEngine: Return execution result
                AgentEngine->>AuditLog: Record SecurityAuditLogEntry
                AgentEngine-->>Client: Return verified response
            end
        end
    end
```

---

## 4. GDPR 72-Hour Incident Response Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant DE as NIST Detect (Telemetry / Guardrails)
    participant RS as NIST Respond (Incident Response Team)
    participant DPO as Data Protection Officer (Zaragoza)
    participant AEPD as Sede Electrónica AEPD (Spain)
    participant Consumers as Affected Consumers (CCPA/GDPR)

    DE->>RS: T=0h: Suspicious Data Extraction / Breach Alert Triggered
    RS->>RS: T<=4h: Containment: Revoke Tokens, Block IPs, Isolate Pods
    RS->>DPO: T<=12h: Triaging Report: Data Classification & Affected Records
    DPO->>DPO: T<=36h: Rights & Freedoms Risk Assessment (GDPR Art. 33)
    alt High Risk to Individuals
        DPO->>AEPD: T<=72h: Formal Electronic Notification to AEPD (Art. 33)
        DPO->>Consumers: Transparent Breach Notice to Affected Individuals (Art. 34 / CCPA)
    else Low Risk (Encrypted / Tokenized)
        DPO->>DPO: Document Incident in Internal Breach Register (Art. 33.5)
    end
```

---

## 5. Storage & Persistence Considerations

1. **In-Memory Thread-Safe Review Queue**: `HITLApprovalRequest` objects are maintained in thread-safe memory with concurrent lock protection, supporting high-throughput evaluation and supervisor resolution.
2. **Deterministic Audit Trail**: Audit entries are formatted in standardized JSON and persisted to structured log streams and security audit archives.
3. **Stateless Governance Endpoints**: Governance endpoints read canonical definitions directly from validated JSON artifacts in the repository specifications directory, guaranteeing zero drift between documentation and runtime APIs.
