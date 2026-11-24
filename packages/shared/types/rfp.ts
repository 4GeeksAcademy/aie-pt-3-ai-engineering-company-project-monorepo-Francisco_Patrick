/**
 * Shared Data Transfer Objects (DTOs) and domain contracts for the RFP Intake & Agentic Analysis Pipeline.
 *
 * Defines contracts shared between `services/api` (REST API) and `uis/backoffice` (Web UI).
 */

/**
 * Standard processing lifecycle statuses for an RFP intake and proposal generation ticket.
 */
export type TicketStatus =
  | "analizando"
  | "descartado"
  | "analisis_completo"
  | "generando_borrador"
  | "en_evaluación"
  | "needs_human_review"
  | "esperando_aprobación"
  | "terminado";

/**
 * Human review approval status for an individual department section in Part 3.
 */
export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "needs_human_review";

/**
 * Valid human reviewer operational decisions in Part 3.
 */
export type ApprovalDecision = "approve" | "reject" | "request_changes";

/**
 * Canonical conflict trigger identifiers evaluated by the deterministic arbitration node (§7).
 */
export type ArbitrationTriggerId =
  | "volume-vs-capacity"
  | "returns-sla-breach"
  | "currency-mismatch";

/**
 * Named TrackFlow arbiters responsible for deterministic conflict resolution.
 */
export type ArbiterName = "Miguel Torres" | "Sofía Ramos";

/**
 * Lifecycle statuses for an individual department proposal section in Part 2.
 */
export type DepartmentSectionStatus =
  | "pending"
  | "drafting"
  | "under_evaluation"
  | "passed"
  | "needs_human_review";

/**
 * Canonical briefing compliance rule identifiers enforced in Part 2 (§5).
 */
export type ComplianceRuleId =
  | "RULE-CURRENCY"
  | "RULE-SLA"
  | "RULE-RETURNS-TIME"
  | "RULE-DISCOUNT-TIERS"
  | "RULE-CARRIER-RATES";

/**
 * Allowed client operating countries per TrackFlow briefing.
 */
export type ClientCountry = "US" | "ES";

/**
 * Supported operating currencies strictly aligned with operating countries.
 */
export type OperatingCurrency = "USD" | "EUR";

/**
 * Valid fulfillment department identifiers.
 */
export type DepartmentId = "warehouse" | "lastmile" | "reverse";

/**
 * Readability metrics calculated from the converted Markdown proposal.
 */
export interface ReadabilityScoresDTO {
  /** Flesch Reading Ease score (0 - 100). */
  flesch_reading_ease: number;
  /** Flesch-Kincaid Grade Level (US grade level). */
  flesch_kincaid_grade: number;
  /** Qualitative readability classification label (e.g. "Standard", "Difficult"). */
  reading_level_label: string;
  /** Total document word count. */
  word_count: number;
  /** Total document sentence count. */
  sentence_count: number;
}

/**
 * Extracted commercial parameters and metadata for an RFP proposal.
 */
export interface RFPMetadataDTO {
  /** Name of the prospective client organization. */
  client_name: string;
  /** Operating country (US or ES). */
  client_country: ClientCountry;
  /** Operating currency (USD or EUR). */
  currency: OperatingCurrency;
  /** List of logistics services requested by the prospect. */
  services_requested: string[];
  /** Expected monthly order volume if specified in document. */
  monthly_volume: number | null;
  /** Proposal submission deadline if specified. */
  deadline: string | null;
  /** Indicated client budget range or pricing expectation. */
  budget_range: string | null;
  /** Fulfillment departments required to service this proposal. */
  departments_needed: DepartmentId[];
  /** Requested services outside TrackFlow's fulfillment capabilities. */
  unsupported_services: string[];
  /** Embedded readability metrics. */
  readability_scores: ReadabilityScoresDTO;
}

/**
 * Readability dimension evaluation outcome for a generated department proposal section.
 */
export interface ReadabilityEvaluationDTO {
  /** Whether the draft passed the readability threshold. */
  pass_status: boolean;
  /** Calculated Flesch Reading Ease score. */
  score: number;
  /** Qualitative diagnostics and grade level details. */
  details: string;
}

/**
 * Relevance dimension evaluation outcome verifying coverage of Part 1 key_aspects.
 */
export interface RelevanceEvaluationDTO {
  /** Whether all required key aspects were addressed. */
  pass_status: boolean;
  /** List of required operational aspects missing from the draft. */
  missing_aspects: string[];
}

/**
 * Compliance dimension evaluation outcome enforcing the 5 TrackFlow briefing rules (§5).
 */
export interface ComplianceEvaluationDTO {
  /** Whether the draft complied with all applicable briefing rules. */
  pass_status: boolean;
  /** Violated rule identifiers (empty when pass_status is true). */
  rule_ids: ComplianceRuleId[];
  /** Human-readable violation descriptions. */
  violations: string[];
}

/**
 * Multi-dimensional evaluation result emitted by a department evaluator for a draft iteration.
 */
export interface EvaluationResultDTO {
  /** Evaluated department identifier. */
  department_id: DepartmentId;
  /** Draft attempt iteration number (1..3). */
  iteration: number;
  /** Readability evaluation outcome. */
  readability: ReadabilityEvaluationDTO;
  /** Requirement relevance evaluation outcome. */
  relevance: RelevanceEvaluationDTO;
  /** Commercial compliance evaluation outcome. */
  compliance: ComplianceEvaluationDTO;
  /** Overall pass flag (true only if readability, relevance, and compliance all pass). */
  overall_pass: boolean;
  /** Actionable feedback instructions passed back to the generator when overall_pass is false. */
  feedback_for_generator: string;
  /** UTC ISO timestamp when evaluation completed. */
  evaluated_at: string;
}

/**
 * Department-specific operational analysis, generated draft content, and evaluation status.
 */
export interface DepartmentSectionDTO {
  /** Optional section UUID. */
  id?: string;
  /** Optional parent ticket UUID. */
  ticket_id?: string;
  /** Department identifier. */
  department_id: DepartmentId;
  /** Full department name (e.g. "Operaciones de Almacén"). */
  department_name: string;
  /** Department lead responsible for the area. */
  responsible_person: string;
  /** Operational key aspects and cost drivers. */
  key_aspects: Record<string, unknown>;
  /** Missing operational parameters captured for follow-up (zero fabrication). */
  open_questions: string[];
  /** Warnings and policy caveats regarding customer requests. */
  policy_warnings: string[];
  /** Current section drafting/evaluation lifecycle status (Part 2). */
  status?: DepartmentSectionStatus;
  /** Current draft generation attempt counter (0..3). */
  iteration?: number;
  /** Generated Markdown proposal draft section text (Part 2). */
  draft_content?: string | null;
  /** Latest structured multi-dimensional evaluation result (Part 2). */
  latest_evaluation?: EvaluationResultDTO | null;
  /** Full evaluation history across iterations. */
  evaluation_results?: EvaluationResultDTO[];
  /** Current human approval state in Part 3 ("pending" | "approved" | "rejected" | "changes_requested"). */
  approval_status?: ApprovalStatus;
  /** Name of the human approver recording the decision. */
  approver?: string | null;
  /** Optional revision feedback provided during human review. */
  review_feedback?: string | null;
  /** UTC ISO timestamp of final approval. */
  approved_at?: string | null;
}

/**
 * Request payload for resuming an interrupted department approval branch in Part 3.
 */
export interface ResumeDecisionRequestDTO {
  /** Active department branch being resumed. */
  department_id: DepartmentId;
  /** Human reviewer operational decision. */
  decision: ApprovalDecision;
  /** Name of the responsible department lead (Ana Whitfield, Carlos Vega, Sofía Ramos). */
  approver: string;
  /** Mandatory feedback if decision is 'request_changes' or 'reject'. */
  feedback?: string;
}

/**
 * Response payload returned upon resuming an interrupted department approval branch.
 */
export interface ResumeDecisionResponseDTO {
  /** Ticket UUID. */
  ticket_id: string;
  /** Resumed department identifier. */
  department_id: DepartmentId;
  /** Updated section approval status. */
  approval_status: ApprovalStatus;
  /** Current overall ticket status. */
  ticket_status: TicketStatus;
  /** Human-readable status summary. */
  message: string;
  /** UTC ISO approval timestamp if approved. */
  approved_at?: string | null;
}

/**
 * Structured metadata detailing before/after state diff and assigned remediation in arbitration.
 */
export interface ArbitrationResolutionDetailsDTO {
  /** Affected departments involved in the conflict. */
  affected_departments: DepartmentId[];
  /** Action taken by the deterministic arbitration rule. */
  action_taken: string;
  /** Capped volume enforced when volume-vs-capacity triggers. */
  capped_volume?: number | null;
  /** Enforced canonical currency when currency-mismatch triggers. */
  enforced_currency?: OperatingCurrency | null;
  /** Additional rule context fields. */
  [key: string]: unknown;
}

/**
 * Audit log record produced by the deterministic conflict arbitration node (Part 3).
 */
export interface ArbitrationLogDTO {
  /** Unique arbitration log record UUID. */
  id: string;
  /** Associated RFP ticket UUID. */
  ticket_id: string;
  /** Canonical conflict trigger ID. */
  trigger_id: ArbitrationTriggerId;
  /** Named authorized arbiter (Miguel Torres or Sofía Ramos). */
  arbiter: ArbiterName;
  /** Explicit statement of the business rule applied. */
  rule_applied: string;
  /** Structured diff and resolution parameters. */
  resolution_details: ArbitrationResolutionDetailsDTO;
  /** UTC ISO timestamp of arbitration execution. */
  created_at: string;
}

/**
 * List response wrapper for ticket arbitration log records.
 */
export interface ArbitrationLogListResponseDTO {
  /** Recorded arbitration audit log entries. */
  items: ArbitrationLogDTO[];
  /** Total count of arbitration logs for the ticket. */
  total: number;
}

/**
 * Approved department section entry within the consolidated FinalDocument.
 */
export interface FinalDocumentSectionEntryDTO {
  /** Display name of the department. */
  department_name: string;
  /** Responsible department lead. */
  responsible_person: string;
  /** Final approved Markdown proposal content. */
  approved_content: string;
  /** UTC ISO timestamp of section approval. */
  approved_at: string;
}

/**
 * Complete, consolidated commercial proposal document synthesized upon 100% department approval (Part 3).
 */
export interface FinalDocumentDTO {
  /** Final document UUID. */
  id: string;
  /** Originating RFP ticket UUID. */
  ticket_id: string;
  /** Proposal document title. */
  title: string;
  /** Prospect client organization name. */
  client_name: string;
  /** Operating currency (USD or EUR). */
  currency: OperatingCurrency;
  /** Consolidated executive summary of the commercial offering. */
  executive_summary: string;
  /** Map of department_id to approved section content and sign-off metadata. */
  sections: Partial<Record<DepartmentId, FinalDocumentSectionEntryDTO>>;
  /** UTC ISO timestamp when the final document was synthesized. */
  generated_at: string;
}

/**
 * Node execution trace entry recorded in LangGraph state (Part 3).
 */
export interface ExecutionTraceEntryDTO {
  /** Canonical graph node or agent name. */
  node_name: string;
  /** Optional department scope if executed on a parallel branch. */
  department_id?: DepartmentId | null;
  /** Serialized snapshot of relevant input data. */
  input_state: Record<string, unknown>;
  /** Serialized snapshot of node outputs. */
  output_state: Record<string, unknown>;
  /** UTC ISO execution timestamp. */
  timestamp: string;
}

/**
 * Immediate response payload returned when triggering Part 2 proposal generation (HTTP 202).
 */
export interface ProposalGenerationAcceptedResponseDTO {
  /** UUID of the ticket entering proposal generation. */
  ticket_id: string;
  /** Updated ticket status ("generando_borrador"). */
  status: TicketStatus;
  /** Confirmation message. */
  message: string;
  /** Active departments queued for drafting and evaluation. */
  active_departments: DepartmentId[];
}

/**
 * Per-department section bundle packaged into the Part 3 handoff payload.
 */
export interface Part3DepartmentSectionBundleDTO {
  /** Finalized or latest draft Markdown content. */
  draft_content: string;
  /** Final section outcome status ("passed" | "needs_human_review"). */
  status: "passed" | "needs_human_review";
  /** Total iterations executed for this section (1..3). */
  iteration: number;
  /** Final structured evaluation outcome. */
  evaluation_result: EvaluationResultDTO;
}

/**
 * Canonical Part 3 handoff payload emitted upon completion of Part 2 proposal generation.
 */
export interface Part3HandoffPayloadDTO {
  /** UUID of the ticket. */
  ticket_id: string;
  /** Semantic schema version ("2.0.0"). */
  schema_version: string;
  /** Overall handoff status ("passed" if all active sections passed, else "needs_human_review"). */
  overall_status: "passed" | "needs_human_review";
  /** Snapshot of RFP metadata. */
  rfp_metadata: {
    client_name: string;
    client_country: ClientCountry;
    currency: OperatingCurrency;
    monthly_volume?: number | null;
    deadline?: string | null;
    departments_needed: DepartmentId[];
  };
  /** Map of active department_id to its finalized section draft and evaluation bundle. */
  department_sections: Partial<Record<DepartmentId, Part3DepartmentSectionBundleDTO>>;
  /** UTC ISO timestamp when the Part 3 handoff payload was emitted. */
  emitted_at: string;
}

/**
 * Internal TrackFlow contact assigned to review or support proposal generation.
 */
export interface InternalContactDTO {
  /** Contact full name. */
  name: string;
  /** Organizational role. */
  role: string;
  /** Department or area of responsibility. */
  department: string;
}

/**
 * Sales executive synthesis and policy contradiction checks.
 */
export interface SalesSynthesisDTO {
  /** Executive summary tailored for Sales Account Managers (e.g. Miguel Torres). */
  executive_summary: string;
  /** Contradictions detected against TrackFlow operating rules or SLAs. */
  flagged_contradictions: string[];
  /** Consolidated questions to ask the prospect during intake calls. */
  key_questions_for_prospect: string[];
  /** Recommended internal stakeholders to consult. */
  internal_contacts: InternalContactDTO[];
}

/**
 * Immutable canonical handoff payload passed to Part 2 (Proposal Generation).
 */
export interface IntakeHandoffPayloadDTO {
  /** UUID of the completed intake ticket. */
  ticket_id: string;
  /** Handoff contract schema version (e.g. "1.0.0"). */
  schema_version: string;
  /** Executive summary tailored for Sales Account Managers (e.g. Miguel Torres). */
  executive_summary: string;
  /** Contradictions detected against TrackFlow operating rules or SLAs. */
  flagged_contradictions: string[];
  /** Consolidated questions to ask the prospect during intake calls. */
  key_questions_for_prospect: string[];
  /** Recommended internal stakeholders to consult. */
  internal_contacts: InternalContactDTO[];
  /** Complete serialized bundle for Part 2 conforming to handoff schema. */
  full_handoff_json: Record<string, unknown>;
  /** UTC ISO timestamp when handoff was created/emitted. */
  created_at?: string;
  /** UTC ISO timestamp when emitted. */
  emitted_at?: string;
}

/**
 * Immediate response payload returned upon PDF upload acceptance (HTTP 202).
 */
export interface IntakeTicketAcceptedResponseDTO {
  /** Unique UUID of the created ticket. */
  ticket_id: string;
  /** Human-readable ticket reference code (e.g. "RFP-2026-001"). */
  ticket_number: string;
  /** Initial processing status ("analizando"). */
  status: TicketStatus;
  /** Informational message confirming background processing. */
  message: string;
  /** UTC ISO creation timestamp. */
  created_at: string;
}

/**
 * Summary view of an RFP intake ticket for list views.
 */
export interface IntakeTicketSummaryDTO {
  /** Ticket UUID. */
  ticket_id: string;
  /** Human-readable ticket number. */
  ticket_number: string;
  /** Current processing status. */
  status: TicketStatus;
  /** Original uploaded PDF filename. */
  raw_pdf_filename: string;
  /** Prospective client name if already extracted. */
  client_name: string | null;
  /** Rejection reason if classified as non-RFP. */
  rejection_reason: string | null;
  /** UTC ISO creation timestamp. */
  created_at: string;
  /** UTC ISO last update timestamp. */
  updated_at: string;
}

/**
 * List response wrapper for tickets.
 */
export interface IntakeTicketListResponseDTO {
  /** List of ticket summaries. */
  items: IntakeTicketSummaryDTO[];
  /** Total count matching query. */
  total: number;
}

/**
 * Detailed view of an RFP intake ticket with complete analysis outputs.
 */
export interface IntakeTicketDetailResponseDTO {
  /** Ticket UUID. */
  ticket_id: string;
  /** Human-readable ticket number. */
  ticket_number: string;
  /** Current processing status. */
  status: TicketStatus;
  /** Original uploaded PDF filename. */
  raw_pdf_filename: string;
  /** Uploaded file size in bytes. */
  file_size_bytes: number;
  /** Rejection explanation if discarded by classifier. */
  rejection_reason: string | null;
  /** Sanitized error diagnostic if background pipeline crashed. */
  error_message: string | null;
  /** Extracted commercial metadata if genuine RFP. */
  metadata: RFPMetadataDTO | null;
  /** Domain sections generated by department workers. */
  department_sections: DepartmentSectionDTO[];
  /** Canonical handoff payload if analysis is complete. */
  handoff: IntakeHandoffPayloadDTO | null;
  /** Deterministic arbitration audit logs recorded during Part 3. */
  arbitration_logs?: ArbitrationLogDTO[];
  /** Consolidated final proposal document if 100% approved in Part 3. */
  final_document?: FinalDocumentDTO | null;
  /** UTC ISO creation timestamp. */
  created_at: string;
  /** UTC ISO last update timestamp. */
  updated_at: string;
}

/**
 * Standard error response envelope.
 */
export interface ErrorResponseDTO {
  /** Sanitized error description. */
  detail: string;
}
