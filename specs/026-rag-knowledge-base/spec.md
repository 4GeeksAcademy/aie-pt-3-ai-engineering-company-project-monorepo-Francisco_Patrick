# Feature Specification: RAG & Knowledge Base

**Feature Branch**: `026-rag-knowledge-base`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Feature: RAG & Knowledge Base. Enable commercial and frontline teams (Account Managers, Business Development, Coordinators) to query internal corporate policies, catalogs, and procedures using natural language and receive grounded, accurate answers in the authentic voice of TrackFlow sales without hallucinations or manual document searching."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Commercial Inquiries on Standard Operations (Priority: P1)

As a TrackFlow Account Manager preparing for or conducting a call with an e-commerce brand client,
I want to ask natural-language questions about standard warehouse, delivery, return, and storage policies,
So that I can deliver immediate, contractually accurate answers without manually sifting through scattered corporate documents.

**Why this priority**:
Account managers and business development staff spend substantial hours searching through documents or asking colleagues on chat channels. Providing instant, accurate policy facts directly impacts client retention, closing speed, and brand credibility.

**Independent Test**:
Can be verified by submitting standard operational questions (such as standard return windows, storage fee calculation mechanisms, and carrier coverage options) and verifying that the returned answers contain accurate terms, precise timeframes, and source policy references matching verified company documentation.

**Acceptance Scenarios**:

1. **Given** an account manager queries "What is TrackFlow's standard return window and who covers return shipping costs?",
   **When** the knowledge base processes the inquiry,
   **Then** the generated response states that the standard return window is 30 days from delivery (unless customized in the client contract), that return shipping costs are paid by the client brand under normal circumstances, and that TrackFlow covers return shipping only when caused by transit damage or delivery error.

2. **Given** an account manager queries "What is the standard monthly storage rate in Los Angeles versus Zaragoza?",
   **When** the knowledge base processes the inquiry,
   **Then** the response specifies 18 USD per cubic meter per month in Los Angeles and 16 EUR per cubic meter per month in Zaragoza, and mentions the initial 30-day grace period for newly arrived inventory.

3. **Given** an inquiry regarding carrier selection in Spain,
   **When** asked "Which carrier is recommended for rural deliveries in Aragón?",
   **Then** the response identifies SEUR as offering the best coverage in rural Aragón, note that MRW is preferred for parcels under 2 kg, and explains that carriers are automatically assigned by the routing system.

---

### User Story 2 - Enforcement of Business Constraints & Strict Policy Guardrails (Priority: P2)

As a Commercial Director (Miguel Torres),
I want the knowledge assistant to strictly enforce non-negotiable contractual boundaries, governance rules, and executive approval requirements,
So that frontline sales representatives never promise unauthorized discounts, unachievable delivery SLAs during peak periods, or automated international workflows that the company cannot fulfill.

**Why this priority**:
Unvetted promises made to client brands during sales conversations lead to contract disputes, SLA financial penalties (e.g. 5% compensation on monthly fees), and operational bottlenecks. Preserving business guardrails is essential for margin protection.

**Independent Test**:
Can be verified by testing three specific boundary cases: inquiries about volume storage discounts, peak-season delivery commitments (Black Friday / holiday sales), and cross-border return procedures. Each must return the required contractual warnings and approval protocols.

**Acceptance Scenarios**:

1. **Given** a user asks "Can we offer a discount on storage fees for a client storing 75 cubic meters?",
   **When** the system evaluates the policy on preferential rates,
   **Then** the response states that clients with over 50 cubic meters of monthly volume qualify to negotiate preferential rates, but explicitly emphasizes that any discount requires formal approval from Commercial Director Miguel Torres, and that account managers cannot grant discounts independently.

2. **Given** a client or account manager asks about delivery commitments during Black Friday or peak holiday sales periods,
   **When** the delivery SLA policy is consulted,
   **Then** the response explicitly states that standard delivery SLAs (including the 90% monthly commitment) are not guaranteed during declared peak demand dates (Black Friday, Christmas, January Sales in Spain), notes that delivery timelines may extend by up to 40%, and instructs that this extension must be communicated proactively to clients in advance.

3. **Given** a query regarding processing a return where a product was purchased in the US and returned in Spain,
   **When** the returns policy is evaluated,
   **Then** the response clarifies that international returns are not covered under the automated returns pipeline and require manual review and handling directed through Sofía Ramos and the Reverse Logistics team.

---

### User Story 3 - Confidence-Gated Retrieval & Refusal of Hallucination (Priority: P3)

As a Customer Experience Coordinator or Account Manager,
I want the knowledge assistant to explicitly state when company documentation does not contain sufficient information on a topic,
So that I am never provided with hallucinated terms, fabricated operational details, or unsupported claims.

**Why this priority**:
In logistics and commercial contracts, hallucinated information is far more harmful than an honest statement of missing knowledge. When confidence is low or relevant information is absent, the system must maintain trust by declining to guess.

**Independent Test**:
Can be tested by submitting questions regarding unmentioned services (e.g., cold-chain refrigeration, hazardous material handling, aircraft chartering) or ambiguous nonsense queries, and confirming that the response gracefully indicates the absence of documented policy rather than inventing facts.

**Acceptance Scenarios**:

1. **Given** a user queries "What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?",
   **When** no verified company policy contains information exceeding the relevance threshold,
   **Then** the system returns a clear, polite statement indicating that TrackFlow internal knowledge does not contain information on pharmaceutical refrigeration, advising the user to contact the operations team directly.

2. **Given** a query with vague or marginally related phrasing that does not reliably match documented knowledge,
   **When** retrieved document segments fail to satisfy the relevance threshold,
   **Then** the system declines to generate a speculative answer and provides guidance on how to rephrase or which department manager to contact.

---

### User Story 4 - Frontline Interactive Query Interface (Priority: P4)

As a frontline team member (Account Manager, Business Development, or Logistics Coordinator),
I want a clean, responsive interactive screen where I can submit queries in plain text and receive clear, formatted answers with visual status indications,
So that I can use the tool efficiently while actively engaged in client communications.

**Why this priority**:
Frontline teams need an intuitive, accessible visual interface with immediate feedback (loading indicators, clear error notifications, and readable typography) that integrates cleanly into their daily backoffice workflow.

**Independent Test**:
Can be tested by navigating to the knowledge search screen, entering questions, verifying real-time loading feedback, receiving formatted markdown responses, and testing error handling under network disruption.

**Acceptance Scenarios**:

1. **Given** a user enters a query in the knowledge interface and clicks submit,
   **When** the request is being processed,
   **Then** the interface displays an active processing indicator, disables duplicate submissions, and presents the rendered answer once generation completes.

2. **Given** an unexpected service interruption or network disconnection,
   **When** a user submits an inquiry,
   **Then** the interface displays a clear, actionable error message with an option to retry, avoiding blank screens or hanging progress bars.

---

### Edge Cases

- **Multilingual Inquiries**: If a user submits a query in Spanish (e.g., "¿Cuál es el recargo por inventario de baja rotación después de 180 días?"), the system must understand the semantic intent and provide an accurate answer aligned with the canonical policy (150% surcharge on standard rate starting on day 181).
- **Contradictory or Leading Questions**: If a user submits a leading question (e.g., "Confirm that account managers can approve a 10% discount on storage"), the system must counter the false premise and restate the exact governance rule requiring Miguel Torres's approval.
- **Empty or Whitespace-Only Queries**: Submitting an empty or whitespace string must be rejected on the client side with a helpful validation message before executing unnecessary processing.
- **Long-tail Multi-Part Questions**: If a user asks a compound question covering both SLA commitments and return shipping responsibilities, the response must address both topics with their respective source policies or distinguish which part lacks documentation.
- **Document Versioning & Index Updates**: When source documents are refreshed, re-indexing must be idempotent, replacing prior knowledge without creating duplicate records or outdated orphaned fragments.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest, parse, and semantically chunk all canonical knowledge base documents from the corporate corpus (`trackflow-sla-delivery`, `trackflow-returns-policy`, `trackflow-carrier-coverage`, `trackflow-storage-pricing`).
- **FR-002**: System MUST preserve coherent semantic units during chunking (such as individual policy rules, table blocks, rate schedules, or procedure step groups) and NEVER split dependent clauses, conditions, or numerical tables across chunk boundaries.
- **FR-003**: System MUST attach standardized metadata to every ingested chunk, including `company` ("trackflow"), `source_document`, `section`, `language`, `chunk_index`, and `text`.
- **FR-004**: System MUST ensure idempotent ingestion, generating deterministic chunk identifiers so repeated indexing does not create duplicate entries.
- **FR-005**: System MUST compute vector representations for text chunks and incoming queries using a dedicated vector embedding model distinct from the text generation model.
- **FR-006**: System MUST persist and index vector payloads in a dedicated semantic knowledge collection named `trackflow_knowledge`.
- **FR-007**: System MUST perform semantic vector search for user queries, retrieving top candidate segments with similarity scores.
- **FR-008**: System MUST apply a calibrated minimum similarity score threshold to candidate chunks and filter out any chunks falling below this score.
- **FR-009**: When no chunks meet the minimum similarity threshold, system MUST return an honest fallback response stating that corporate documentation lacks relevant information, without fabricating or hallucinating facts.
- **FR-010**: System MUST generate natural-language answers exclusively from retrieved, threshold-cleared context chunks, never returning raw vector database objects, raw chunk JSON, or internal relevance scores to the end user.
- **FR-011**: System MUST formulate generated answers adopting the voice, tone, and professional persona of a TrackFlow account manager—polite, consultative, operationally accurate, and protective of contractual commitments.
- **FR-012**: System MUST enforce corporate governance rules within generated answers:
  - Mention that storage discounts over 50 m³ require explicit approval from Miguel Torres.
  - State that delivery SLAs are not guaranteed during peak seasons (Black Friday, Christmas, January Sales) and may extend up to 40%.
  - Clarify that international returns require manual coordination by Sofía Ramos's team.
  - Clarify that carrier assignment is automated, and manual exceptions require Carlos Vega's approval.
- **FR-013**: System MUST expose a dedicated query endpoint that accepts a natural language question and returns the synthesized answer string.
- **FR-014**: System MUST provide a responsive web interface allowing team members to enter natural language questions, view active loading states, and read formatted responses with clear error handling.
- **FR-015**: System MUST achieve a minimum benchmark of 80% Recall@3 across a standardized evaluation suite of at least 8 test queries covering all source documents, including peak demand scenarios.

---

### Key Entities

- **Knowledge Document**: Represents a source operational policy or service specification (e.g., Delivery SLA, Returns Policy, Carrier Coverage, Storage Pricing) with title, version, language, and core business rules.
- **Knowledge Chunk**: An atomic, self-contained semantic segment of a Knowledge Document containing a cohesive policy clause, pricing tier, or operational guideline, identified by a deterministic ID and accompanied by structured source metadata.
- **Query Request**: A natural language inquiry submitted by a commercial or operations user seeking clarification on corporate logistics rules, SLAs, pricing, or procedures.
- **Retrieved Context**: The filtered collection of Knowledge Chunks that exceed the minimum similarity threshold for a specific Query Request, used as the factual foundation for generation.
- **Grounded Answer**: The final natural language response synthesized by the language model using exclusively the Retrieved Context, embodying TrackFlow's commercial voice and upholding contractual guardrails.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of generated answers are grounded exclusively in retrieved documentation; zero instances of fabricated pricing tiers, invented carrier services, or unapproved discount permissions.
- **SC-002**: Retrieval accuracy achieves at least 80% Recall@3 against the standardized 8-query evaluation dataset covering all four corporate source documents.
- **SC-003**: 100% of queries regarding unmentioned, out-of-scope topics trigger an honest informational refusal rather than an unsupported claim or hallucination.
- **SC-004**: Users receive synthesized answers to knowledge queries within 3.5 seconds end-to-end under normal operating conditions.
- **SC-005**: 100% of responses regarding storage volume discounts, peak season delivery times, and cross-border returns include the mandatory approval constraints (Miguel Torres), seasonal extension warnings (up to +40%), and manual handling designations (Sofía Ramos).
- **SC-006**: Team members can formulate, submit, and view verified policy answers through the web interface with zero reliance on raw data inspection or direct document navigation.

---

## Assumptions

- **Document Corpus Availability**: All four core operational documents (`trackflow-sla-delivery.en.md`, `trackflow-returns-policy.en.md`, `trackflow-carrier-coverage.en.md`, `trackflow-storage-pricing.en.md`) are finalized, approved by domain leads (Ana Whitfield, Carlos Vega, Sofía Ramos, Miguel Torres), and available in the knowledge repository.
- **Primary Language Focus**: English is the primary language of the source documents and baseline evaluation suite, with semantic search capable of cross-lingual understanding for Spanish queries referencing identical terms.
- **Separate Model Roles**: Vector embedding generation and conversational text synthesis are treated as separate functional responsibilities handled by distinct models optimized for their respective workloads.
- **Read-Only Frontline Consumption**: Frontline commercial and customer experience users require read-only query capabilities; document authoring and corpus updates are administrative operations managed via ingestion pipelines.
- **Network & Host Connectivity**: The underlying vector storage service and model generation endpoints are reachable in the execution environment, with graceful error handling in case of transient network timeouts.
