/**
 * Shared Data Transfer Objects (DTOs) and domain contracts for the RFP Intake & Agentic Analysis Pipeline.
 *
 * Defines contracts shared between `services/api` (REST API) and `uis/backoffice` (Web UI).
 */

/**
 * Standard processing lifecycle statuses for an RFP intake ticket.
 */
export type TicketStatus = "analizando" | "descartado" | "analisis_completo";

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
 * Department-specific operational analysis and zero-hallucination open questions.
 */
export interface DepartmentSectionDTO {
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
