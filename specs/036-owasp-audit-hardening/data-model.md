# Data Model: TrackFlow OWASP Top 10 Security Audit, Infrastructure Hardening, and Critical Remediation

**Feature Branch**: `feature/owasp-top10-audit`  
**Specification**: [specs/036-owasp-audit-hardening/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/spec.md)  
**Date**: 2026-11-25  

---

## 1. Entities & Schema Definitions

### 1.1 SecurityFinding

Represents an audited vulnerability or infrastructure hardening deficiency evaluated against the OWASP Top 10 (2021) and host baseline requirements.

```mermaid
classDiagram
    class SecurityFinding {
        +string id
        +ComponentCategory component
        +OWASPCategory category
        +string title
        +string description
        +string location
        +SeverityLevel severity
        +ApplicabilityVerdict applicability
        +boolean gdpr_implications
        +boolean ccpa_implications
        +string remediation_plan
        +VerificationStatus verification_status
        +string verification_proof
        +datetime created_at
        +datetime resolved_at
    }

    class ComponentCategory {
        <<enumeration>>
        BACKEND
        FRONTEND
        AGENTIC
        HOST
    }

    class OWASPCategory {
        <<enumeration>>
        A01_BROKEN_ACCESS_CONTROL
        A02_CRYPTOGRAPHIC_FAILURES
        A03_INJECTION
        A04_INSECURE_DESIGN
        A05_SECURITY_MISCONFIGURATION
        A06_VULNERABLE_COMPONENTS
        A07_AUTH_FAILURES
        A08_INTEGRITY_FAILURES
        A09_LOGGING_MONITORING_FAILURES
        A10_SSRF
    }

    class SeverityLevel {
        <<enumeration>>
        CRITICAL
        HIGH
        MEDIUM
        LOW
        INFORMATIONAL
    }

    class ApplicabilityVerdict {
        <<enumeration>>
        APPLIES
        DOES_NOT_APPLY
    }

    class VerificationStatus {
        <<enumeration>>
        OPEN
        IN_PROGRESS
        VERIFIED_RESOLVED
        MITIGATED
    }

    SecurityFinding --> ComponentCategory
    SecurityFinding --> OWASPCategory
    SecurityFinding --> SeverityLevel
    SecurityFinding --> ApplicabilityVerdict
    SecurityFinding --> VerificationStatus
```

#### Fields & Validation Rules:
- `id`: Non-empty string formatted as `SEC-[COMPONENT]-[0-9]{3}` (e.g. `SEC-BK-001`, `SEC-AG-002`).
- `component`: One of `BACKEND`, `FRONTEND`, `AGENTIC`, `HOST`.
- `category`: Must map to one of the 10 official OWASP Top 10 categories.
- `severity`: Must follow standard CVSS classification: `CRITICAL` ($\ge 9.0$), `HIGH` ($7.0 - 8.9$), `MEDIUM` ($4.0 - 6.9$), `LOW` ($0.1 - 3.9$), or `INFORMATIONAL` ($0.0$).
- `applicability`: When `DOES_NOT_APPLY`, `remediation_plan` documents why the risk is mitigated or architecturally absent. When `APPLIES`, `location` and `remediation_plan` are mandatory.
- `gdpr_implications`: `true` if vulnerability could lead to unauthorized disclosure of B2C personal data or breach of the 72-hour AEPD notification window.
- `ccpa_implications`: `true` if vulnerability impacts California consumer personal information or opt-out rights.
- `verification_proof`: Mandatory for any finding with severity `CRITICAL` prior to closing (`verification_status = VERIFIED_RESOLVED`).

---

### 1.2 AuditScopeRecord

Represents a distinct service or subsystem subject to security audit verification under FR-002.

```mermaid
classDiagram
    class AuditScopeRecord {
        +string service_id
        +string service_name
        +string repository_path
        +string engineering_owner
        +DataClassification data_classification
        +List~RegulatoryFramework~ regulatory_scope
        +string runtime_environment
    }

    class DataClassification {
        <<enumeration>>
        RESTRICTED_PII
        CONFIDENTIAL_B2B
        INTERNAL_OPERATIONAL
        PUBLIC
    }

    class RegulatoryFramework {
        <<enumeration>>
        GDPR_EU
        CCPA_CPRA_US
    }

    AuditScopeRecord --> DataClassification
    AuditScopeRecord --> RegulatoryFramework
```

#### Pre-populated Scope Records:
| Service ID | Service Name | Path | Classification | Frameworks |
|---|---|---|---|---|
| `cx-support-agent` | 24/7 CX Support Agent | `services/api/application/services/support_agent_service.py` | `RESTRICTED_PII` | `[GDPR_EU, CCPA_CPRA_US]` |
| `carrier-selection-engine` | Carrier Selection Engine | `services/api/application/services/` / `mcps/` | `CONFIDENTIAL_B2B` | `[GDPR_EU]` |
| `return-approval-engine` | Return Approval Engine | `services/api/application/services/` | `RESTRICTED_PII` | `[GDPR_EU, CCPA_CPRA_US]` |
| `return-policy-rag` | Return Policy RAG KB | `services/api/application/services/knowledge_service.py` | `CONFIDENTIAL_B2B` | `[GDPR_EU]` |
| `tracking-api` | Public Tracking API | `services/api/presentation/api/v1/` | `RESTRICTED_PII` | `[GDPR_EU, CCPA_CPRA_US]` |
| `operations-dashboard` | Real-time Operations Dashboard | `uis/backoffice/` | `INTERNAL_OPERATIONAL` | `[GDPR_EU]` |
| `b2b-brand-portal` | B2B Customer Brand Portals | `uis/website/` | `CONFIDENTIAL_B2B` | `[GDPR_EU, CCPA_CPRA_US]` |
| `host-server` | Linux Host Server & Network | Host OS / `infra/` | `RESTRICTED_PII` | `[GDPR_EU, CCPA_CPRA_US]` |

---

### 1.3 HostHardeningBaseline

Represents the measurable host and infrastructure security configuration state across pre-remediation and post-remediation phases.

```mermaid
classDiagram
    class HostHardeningBaseline {
        +string profile_id
        +datetime captured_at
        +BaselinePhase phase
        +SSHConfigRecord ssh_config
        +string operational_user
        +List~string~ active_users
        +List~ListeningPortRecord~ listening_ports
        +List~FirewallRuleRecord~ firewall_rules
        +List~FilePermissionRecord~ filesystem_permissions
    }

    class SSHConfigRecord {
        +boolean permit_root_login
        +boolean password_authentication
        +int max_auth_tries
        +int port
        +boolean is_compliant
    }

    class ListeningPortRecord {
        +int port
        +string protocol
        +string process
        +boolean is_allowed_public
    }

    class FirewallRuleRecord {
        +string direction
        +int port
        +string action
        +boolean is_active
    }

    class FilePermissionRecord {
        +string path
        +string expected_mode
        +string actual_mode
        +string owner
        +boolean is_compliant
    }

    HostHardeningBaseline --> SSHConfigRecord
    HostHardeningBaseline --> ListeningPortRecord
    HostHardeningBaseline --> FirewallRuleRecord
    HostHardeningBaseline --> FilePermissionRecord
```

#### Validation Rules:
- `ssh_config.permit_root_login`: Must be `false` in post-remediation baseline (`PermitRootLogin no`).
- `listening_ports`: Only ports `22` (SSH), `80` (HTTP), and `443` (HTTPS) may have `is_allowed_public = true`. All internal service ports (e.g. `8000`, `6379`, `6333`) must bind to `127.0.0.1` or be blocked externally.
- `filesystem_permissions`: All sensitive `.env` files must have `actual_mode` equal to `0600` or `0400` and owner matching `operational_user`.

---

### 1.4 AgentActionPolicy & HumanApprovalGateRecord

Represents the policy enforcement rules and human-in-the-loop audit records for irreversible actions.

```mermaid
classDiagram
    class AgentActionPolicy {
        +AgentActionType action_type
        +float max_autonomous_amount_eur
        +List~string~ allowed_autonomous_statuses
        +boolean require_session_binding
        +boolean enforce_human_approval_gate
    }

    class HumanApprovalGateRecord {
        +string request_id
        +AgentActionType action_type
        +string entity_id
        +string requested_by_session
        +dict payload_snapshot
        +float requested_amount_eur
        +ApprovalStatus status
        +string reviewer_id
        +datetime created_at
        +datetime reviewed_at
        +string decision_notes
    }

    class AgentActionType {
        <<enumeration>>
        RETURN_APPROVAL
        CARRIER_REASSIGNMENT
        ORDER_LOOKUP
        BRAND_METRIC_QUERY
    }

    class ApprovalStatus {
        <<enumeration>>
        AUTONOMOUSLY_APPROVED
        PENDING_HUMAN_APPROVAL
        HUMAN_APPROVED
        HUMAN_REJECTED
        BLOCKED_SECURITY_VIOLATION
    }

    HumanApprovalGateRecord --> AgentActionType
    HumanApprovalGateRecord --> ApprovalStatus
```

#### State Transition Diagram:
```mermaid
stateDiagram-v2
    [*] --> Submitted: Incoming Agent Action
    Submitted --> AUTONOMOUSLY_APPROVED: Policy passes & amount <= 100 EUR & status in allowed
    Submitted --> PENDING_HUMAN_APPROVAL: Policy passes but amount > 100 EUR OR in-transit reassignment
    Submitted --> BLOCKED_SECURITY_VIOLATION: Cross-customer IDOR or prompt injection detected
    
    PENDING_HUMAN_APPROVAL --> HUMAN_APPROVED: Operational reviewer approves
    PENDING_HUMAN_APPROVAL --> HUMAN_REJECTED: Operational reviewer rejects
    
    AUTONOMOUSLY_APPROVED --> [*]
    BLOCKED_SECURITY_VIOLATION --> [*]
    HUMAN_APPROVED --> [*]
    HUMAN_REJECTED --> [*]
```
