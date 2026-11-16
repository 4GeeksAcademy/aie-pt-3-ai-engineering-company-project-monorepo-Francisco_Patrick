/**
 * Shared Data Transfer Objects (DTOs) for TrackFlow RAG & Knowledge Base domain.
 *
 * Defines strict contract interfaces consumed across frontend UIs (`uis/backoffice`)
 * and internal utilities when communicating with `/api/v1/knowledge/*` endpoints.
 */

/**
 * Represents a verifiable citation pointing to a source corporate policy document and section.
 */
export interface KnowledgeSourceCitationDTO {
  /** Canonical source document slug (e.g. "sla-delivery", "returns-policy", "carrier-coverage", "storage-pricing"). */
  source_document: string;
  /** Title or subtitle of the cited section within the source document. */
  section: string;
  /** Cosine similarity score in range [0.0, 1.0]. */
  similarity_score: number;
}

/**
 * Request payload for submitting a natural-language question to the TrackFlow knowledge base.
 */
export interface KnowledgeQueryRequestDTO {
  /** Plain-text natural-language question (3 to 1000 characters). */
  query: string;
  /** Optional ISO 639-1 preferred response language code (defaults to "en"). */
  language?: string | undefined;
  /** Optional maximum number of candidate chunks to retrieve (1 to 10, defaults to 3). */
  top_k?: number | undefined;
  /** Optional minimum similarity score threshold (0.0 to 1.0, defaults to 0.62). */
  min_score?: number | undefined;
}

/**
 * Synthesized grounded response returned by the TrackFlow knowledge base endpoint.
 */
export interface KnowledgeQueryResponseDTO {
  /** Echoed sanitized input query. */
  query: string;
  /** Grounded synthesized natural-language answer in TrackFlow sales persona. */
  answer: string;
  /** True if the inquiry was refused due to low confidence or missing documentation. */
  is_refusal: boolean;
  /** List of verifiable source citations supporting the answer. */
  sources: KnowledgeSourceCitationDTO[];
  /** End-to-end processing time in milliseconds. */
  execution_time_ms: number;
}

/**
 * Operational health and index metrics for the Qdrant knowledge base collection.
 */
export interface KnowledgeHealthResponseDTO {
  /** Operational status indicator of the vector store collection. */
  status: "healthy" | "degraded" | "unhealthy";
  /** Active Qdrant collection name ("trackflow_knowledge"). */
  collection_name: string;
  /** Total number of vector points indexed in the collection. */
  indexed_points_count: number;
  /** Dimensionality of stored embedding vectors (384). */
  vector_dimensions: number;
}
