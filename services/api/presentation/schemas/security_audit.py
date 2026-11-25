"""Pydantic serialization schemas for OWASP Top 10 security audit and Human-in-the-loop gates.

Matches contract schemas:
- contracts/owasp-audit-matrix.schema.json
- contracts/host-hardening-baseline.schema.json
- contracts/agent-guardrail-hitl.schema.json
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditMetadataSchema(BaseModel):
    """Metadata describing the security audit execution and regulatory scope."""

    model_config = ConfigDict(extra="forbid")

    audit_date: str = Field(description="ISO 8601 execution timestamp")
    evaluator: str = Field(description="Evaluation entity or engineer")
    commit_hash: str = Field(description="Git commit hash of evaluated codebase")
    branch: str = Field(description="Branch name")
    regulatory_frameworks: List[Literal["GDPR_EU", "CCPA_CPRA_US"]] = Field(
        default=["GDPR_EU", "CCPA_CPRA_US"],
        description="Applicable privacy and security frameworks",
    )


class AuditScopeRecordSchema(BaseModel):
    """Subsystem under security audit scope."""

    model_config = ConfigDict(extra="forbid")

    service_id: str
    service_name: str
    repository_path: str
    data_classification: Literal[
        "RESTRICTED_PII", "CONFIDENTIAL_B2B", "INTERNAL_OPERATIONAL", "PUBLIC"
    ]
    engineering_owner: str


class SecurityFindingSchema(BaseModel):
    """Audited vulnerability or hardening item evaluated against OWASP Top 10."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^SEC-(BK|FE|AG|HST)-[0-9]{3}$")
    component: Literal["BACKEND", "FRONTEND", "AGENTIC", "HOST"]
    category: Literal[
        "A01_BROKEN_ACCESS_CONTROL",
        "A02_CRYPTOGRAPHIC_FAILURES",
        "A03_INJECTION",
        "A04_INSECURE_DESIGN",
        "A05_SECURITY_MISCONFIGURATION",
        "A06_VULNERABLE_COMPONENTS",
        "A07_AUTH_FAILURES",
        "A08_INTEGRITY_FAILURES",
        "A09_LOGGING_MONITORING_FAILURES",
        "A10_SSRF",
    ]
    title: str
    location: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]
    applicability: Literal["APPLIES", "DOES_NOT_APPLY"]
    verification_status: Literal["OPEN", "IN_PROGRESS", "VERIFIED_RESOLVED", "MITIGATED"]
    description: Optional[str] = None
    gdpr_implications: Optional[bool] = False
    ccpa_implications: Optional[bool] = False
    remediation_plan: Optional[str] = None
    verification_proof: Optional[str] = None


class OWASPAuditMatrixResponse(BaseModel):
    """Top-level response payload for the tri-track OWASP security audit matrix."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Optional[str] = Field(default=None, alias="$schema")
    audit_metadata: AuditMetadataSchema
    scope_records: List[AuditScopeRecordSchema]
    findings: List[SecurityFindingSchema]


# ---------------------------------------------------------------------------
# Host Hardening Schemas
# ---------------------------------------------------------------------------

class SSHConfigSchema(BaseModel):
    """SSH daemon configuration parameters and compliance indicator."""

    model_config = ConfigDict(extra="forbid")

    permit_root_login: bool
    password_authentication: bool
    max_auth_tries: int = Field(ge=1, le=6)
    port: int = 22
    is_compliant: bool


class ListeningPortSchema(BaseModel):
    """Listening port status and exposure classification."""

    model_config = ConfigDict(extra="forbid")

    port: int
    protocol: Literal["tcp", "udp"]
    process: str
    is_allowed_public: bool
    bind_address: Optional[str] = "0.0.0.0"


class FirewallRuleSchema(BaseModel):
    """Host firewall policy rule."""

    model_config = ConfigDict(extra="forbid")

    direction: Literal["IN", "OUT"]
    port: int
    action: Literal["ALLOW", "DENY", "DROP"]
    is_active: bool


class FilePermissionSchema(BaseModel):
    """Filesystem permission mask and compliance status."""

    model_config = ConfigDict(extra="forbid")

    path: str
    expected_mode: str
    actual_mode: str
    owner: str
    is_compliant: bool


class HostHardeningBaselineResponse(BaseModel):
    """Host infrastructure baseline snapshot response."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    captured_at: str
    phase: Literal["PRE_REMEDIATION", "POST_REMEDIATION"]
    ssh_config: SSHConfigSchema
    operational_user: str
    listening_ports: List[ListeningPortSchema]
    firewall_rules: List[FirewallRuleSchema]
    filesystem_permissions: List[FilePermissionSchema]
    active_users: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Agent Guardrail HITL Schemas
# ---------------------------------------------------------------------------

class SessionContextSchema(BaseModel):
    """Authenticated caller session context."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    authenticated_orders: List[str]
    brand_id: Optional[str] = None
    country: Optional[Literal["US", "ES"]] = None


class ActionParametersSchema(BaseModel):
    """Parameters submitted with an autonomous agent tool action."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    refund_amount_eur: Optional[float] = Field(default=None, ge=0)
    target_carrier: Optional[str] = None
    shipment_status: Optional[str] = None
    return_reason: Optional[str] = None


class EvaluationResultSchema(BaseModel):
    """Policy decision evaluated for the requested action."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "AUTONOMOUSLY_APPROVED",
        "PENDING_HUMAN_APPROVAL",
        "BLOCKED_SECURITY_VIOLATION",
        "REFUSED_OUT_OF_SCOPE",
    ]
    reason_code: Optional[str] = None
    threshold_eur: Optional[float] = None
    human_review_queue_id: Optional[str] = None


class AgentGuardrailHITLPayload(BaseModel):
    """Agent tool call payload with boundary evaluation."""

    model_config = ConfigDict(extra="forbid")

    action_type: Literal[
        "RETURN_APPROVAL",
        "CARRIER_REASSIGNMENT",
        "ORDER_LOOKUP",
        "BRAND_METRIC_QUERY",
    ]
    session_context: SessionContextSchema
    parameters: ActionParametersSchema
    evaluation_result: Optional[EvaluationResultSchema] = None


class HumanApprovalDecisionRequest(BaseModel):
    """Operational reviewer decision payload."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: Optional[str] = None
    approved: bool
    decision_notes: Optional[str] = None


class HumanApprovalGateResponse(BaseModel):
    """Human approval queue record presentation schema."""

    request_id: str
    action_type: str
    entity_id: str
    requested_by_session: str
    payload_snapshot: Dict[str, Any]
    requested_amount_eur: float
    status: str
    reviewer_id: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: str
    reviewed_at: Optional[str] = None
