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


# ---------------------------------------------------------------------------
# NIST CSF 2.0 & AI Governance Schemas
# ---------------------------------------------------------------------------

class AISystemRecordSchema(BaseModel):
    """Authoritative inventory schema of an operational AI component."""

    model_config = ConfigDict(extra="forbid")

    system_id: str = Field(pattern=r"^TF-AI-[0-9]{2}-[A-Z0-9-]+$")
    name: str
    description: str
    repository_path: str
    architecture_type: Literal[
        "AUTONOMOUS_AGENT",
        "DECISION_ENGINE",
        "RAG_PIPELINE",
        "MCP_SERVER_TOOL",
    ]
    custodian_team: str
    technical_lead: str
    data_classification: Literal[
        "RESTRICTED_PII",
        "CONFIDENTIAL_B2B",
        "INTERNAL_OPERATIONAL",
        "PUBLIC_TRANSIT",
    ]
    input_attack_surfaces: List[str]
    requires_hitl_gates: bool
    rate_limiting_enabled: bool
    last_audited_at: str


class SharedResponsibilityRecordSchema(BaseModel):
    """Demarcated security boundaries for external AI providers."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    provider_name: str
    vendor_category: Literal[
        "FOUNDATION_MODEL_API",
        "VECTOR_DATABASE_CLOUD",
        "COURIER_CARRIER_INTEGRATION",
    ]
    service_scope: str
    trackflow_responsibilities: List[str]
    vendor_responsibilities: List[str]
    zero_data_retention_active: bool
    transit_encryption_enforced: bool
    governing_dpa_reference: str


class HITLApprovalRequestSchema(BaseModel):
    """HITL action approval request schema matching NIST governance contract."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    action_type: Literal[
        "RETURN_APPROVAL",
        "HIGH_VALUE_DISPATCH",
        "CARRIER_REASSIGNMENT",
        "CROSS_BRAND_METRIC_SHARE",
    ]
    entity_id: str
    requested_by_session: str
    requested_by_agent: str
    payload_snapshot: Dict[str, Any]
    monetary_impact_eur: Optional[float] = None
    status: Literal[
        "PENDING_HUMAN_APPROVAL",
        "HUMAN_APPROVED",
        "HUMAN_REJECTED",
        "EXPIRED_FAIL_SECURE",
    ]
    reviewer_id: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: str
    expires_at: str
    resolved_at: Optional[str] = None


class HITLReviewDecisionRequest(BaseModel):
    """Review decision payload submitted by supervisor."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    decision: Literal["APPROVE", "REJECT"]
    reviewer_id: Optional[str] = Field(
        default=None,
        description="Optional supervisor ID; ignored/overridden in favor of authenticated JWT user identity (email/id) to prevent spoofing.",
    )
    decision_notes: Optional[str] = None


class ResidualRiskRecordSchema(BaseModel):
    """Documented residual risk record with severity and mitigation milestone."""

    model_config = ConfigDict(extra="forbid")

    risk_id: str = Field(pattern=r"^RISK-NIST-[A-Z]{2}-[0-9]{2}$")
    nist_function: Literal[
        "GOVERN",
        "IDENTIFY",
        "PROTECT",
        "DETECT",
        "RESPOND",
        "RECOVER",
    ]
    description: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    business_impact: str
    compensatory_controls: List[str]
    target_remediation_milestone: str
    risk_owner: str
    status: Literal["ACCEPTED_TEMPORARY", "REMEDIATION_SCHEDULED", "REMEDIATED"]


class NISTControlActionSchema(BaseModel):
    """Operational security control action mapped to a NIST CSF 2.0 category."""

    model_config = ConfigDict(extra="forbid")

    control_id: str
    category_code: str
    title: str
    concrete_operational_action: str
    verification_mechanism: str
    implementation_location: str
    priority: Literal["P1", "P2", "P3"]


class NISTRegulatoryAlignmentSchema(BaseModel):
    """Regulatory privacy compliance indicators."""

    model_config = ConfigDict(extra="forbid")

    gdpr_aepd_72h_sla_compliant: bool
    ccpa_cpra_rights_enforced: bool
    primary_dpo_office: str


class NISTFunctionsSchema(BaseModel):
    """All 6 NIST CSF 2.0 functions."""

    model_config = ConfigDict(extra="forbid")

    GOVERN: List[NISTControlActionSchema]
    IDENTIFY: List[NISTControlActionSchema]
    PROTECT: List[NISTControlActionSchema]
    DETECT: List[NISTControlActionSchema]
    RESPOND: List[NISTControlActionSchema]
    RECOVER: List[NISTControlActionSchema]


class NISTAssessmentReportResponse(BaseModel):
    """Top-level assessment report conforming to contracts/nist-security-schemas.json."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    framework_version: str
    created_at: str
    executive_sponsor: str
    functions: NISTFunctionsSchema
    residual_risks: List[ResidualRiskRecordSchema]
    regulatory_alignment: NISTRegulatoryAlignmentSchema

