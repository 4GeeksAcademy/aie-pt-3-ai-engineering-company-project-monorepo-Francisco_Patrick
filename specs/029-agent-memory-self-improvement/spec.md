# Feature Specification: Agent Memory & Self-Improvement (Part 1 of 2)

**Feature Branch**: `feature/agent-memory`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Ticket #MEM-092: Agent Memory & Self-Improvement (Part 1 of 2) — Extend the existing support agent with persistent memory capabilities so that operator corrections, recurrent incident context, and B2B client preferences are retained across sessions without repeated manual corrections. Enforce storage isolation from company static knowledge (RAG), single-call response generation and memory candidate evaluation, explicit in-conversation user confirmation with intent classification, auditable lifecycle decision logging, bounded memory growth with consolidation, and memory anti-poisoning defenses adhering to trackflow-BRIEFING.es.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single-Call Memory Proposal on Operator Corrections (Priority: P1)

As a TrackFlow Support Specialist or Operations Coordinator in Zaragoza or Los Angeles,
I want the support assistant to evaluate our ongoing conversation, detect when I provide operational corrections or recurring context, and propose saving that context at the end of its response in that same interaction turn,
So that the assistant captures operational knowledge without delay while avoiding extra latency, secondary evaluation agents, or silent, unconfirmed memory persistence.

**Why this priority**:
Currently, support specialists must repeatedly re-explain carrier route changes, recurring incident disruptions, and client reporting preferences across sessions because the assistant lacks cross-session memory. Detecting and proposing memory candidates in the same turn without extra round-trips is the foundational entry point for self-improvement.

**Independent Test**:
Can be verified by submitting an operational carrier coverage correction (e.g., carrier coverage updates in rural areas) and confirming that the assistant generates its normal operational answer, includes a clear memory proposal with confirmation prompt at the end of the response in a single execution turn, and defers saving to persistent storage until confirmation.

**Acceptance Scenarios**:

1. **Given** an operator correcting a carrier route in Zaragoza ("SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month"),
   **When** the assistant processes the message,
   **Then** the assistant generates a helpful response acknowledging the operational instruction, appends an explicit proposal asking for confirmation to record this carrier coverage rule, and leaves persistent storage unmodified pending user response.
2. **Given** an operator explaining a recurring regional incident disruption ("The delays reported across Los Angeles branches this week are due to a port strike, not our fulfillment operations; this is the third ticket on this topic"),
   **When** the assistant processes the explanation,
   **Then** the assistant incorporates the incident context into its response, presents an explicit memory proposal to remember this recurring disruption context, and defers persistence.
3. **Given** an operator sharing a recurring B2B client preference ("The cosmetics brand always requests their monthly performance report with the returns breakdown presented before dispatch volume"),
   **When** the assistant processes the request,
   **Then** the assistant structures the response accordingly and proposes persisting this client-specific reporting preference for future sessions.
4. **Given** an ephemeral, non-memorable interaction (such as a one-off tracking query "Where is package XJ4471?", a polite closing "Perfect, that resolved it", or a one-time utility task "Translate this customer email to English"),
   **When** the assistant generates its response,
   **Then** the assistant answers the request cleanly without generating any memory proposal or confirmation prompt.

---

### User Story 2 - Explicit Intent Classification, Safe Defaults & Auditable Lifecycle (Priority: P1)

As a Support Coordinator or CX Manager,
I want the assistant to classify user follow-ups to memory proposals into explicit outcomes (`approve`, `reject`, `edit`, or `unrelated/ambiguous`), default safely to discarding proposals on ambiguity or topic shifts, maintain at most one pending proposal, and record every proposal lifecycle event in an audit log,
So that no unauthorized or accidental memories are saved, silent or ambiguous responses never trigger persistence, and every memory decision is transparently traceable.

**Why this priority**:
Automated self-improvement without human oversight and strict classification creates hallucinations and drift. If an agent assumes silence or vague responses mean approval, erroneous information contaminates future interactions. Explicit classification, single-queue bounding, safe rejection defaults, and complete audit logging guarantee reliability and enterprise control.

**Independent Test**:
Can be verified by staging an active memory proposal, responding with ambiguous text or a topic switch, verifying that the proposal is discarded with persistent storage untouched, and confirming that an auditable record is logged with timestamp, classification result, and originating message.

**Acceptance Scenarios**:

1. **Given** an active pending memory proposal,
   **When** the user explicitly confirms (e.g., "Yes, remember this rule"),
   **Then** the assistant classifies the intent as `approve`, commits the memory to persistent storage, acknowledges the confirmation to the user, and records an approved event in the audit log.
2. **Given** an active pending memory proposal,
   **When** the user explicitly rejects (e.g., "No, do not save that"),
   **Then** the assistant classifies the intent as `reject`, discards the proposal without writing to memory, and records a rejected event in the audit log.
3. **Given** an active pending memory proposal,
   **When** the user responds with an unrelated inquiry or changes the topic (e.g., "Can you check inventory for SKU-401?"),
   **Then** the assistant classifies the intent as `unrelated/ambiguous`, safely discards the pending proposal without persisting it, logs the discarded decision, and answers the new inquiry in the same turn without blocking the conversation.
4. **Given** an active pending memory proposal,
   **When** a new operational message arrives before the proposal is resolved,
   **Then** the system suppresses the creation of any secondary proposal, strictly preserving a single pending item at a time.
5. **Given** an active pending memory proposal,
   **When** the user provides a modified or edited rule (e.g., "Remember it, but only for packages over 5kg"),
   **Then** the assistant classifies the intent as `edit`, updates the proposal content, logs the edit event, and awaits confirmation for the revised rule before persisting.

---

### User Story 3 - Cross-Session Memory Recall with Strict Storage Isolation (Priority: P1)

As a Support Specialist handling inquiries across consecutive days or shifts,
I want the assistant to automatically recall confirmed operational carrier rules, incident context, and client preferences in future sessions without querying company static documentation collections,
So that support answers reflect learned operational rules immediately while ensuring company reference knowledge remains strictly read-only and unpolluted.

**Why this priority**:
The core business problem reported by operations is that 15 support specialists across two countries must repeatedly re-educate the assistant on carrier constraints. Cross-session recall directly solves this operational friction, while strict storage isolation protects enterprise static knowledge from unauthorized writes.

**Independent Test**:
Can be verified by completing an approved memory cycle for a carrier rule, opening a brand-new user session with a query regarding that carrier and route, and verifying that the assistant autonomously applies the stored memory rule to produce an accurate response, citing the operational memory context without modifying static company knowledge bases.

**Acceptance Scenarios**:

1. **Given** an approved and persisted memory regarding a carrier route change in Zaragoza,
   **When** a user in a subsequent session asks about carrier selection for that destination,
   **Then** the assistant recalls the stored rule and factors it into the recommendation without requiring user re-prompting.
2. **Given** an approved and persisted memory regarding weekly port disruption in Los Angeles,
   **When** a user asks about delayed shipments originating from that hub,
   **Then** the assistant correlates the delay with the remembered disruption context instead of escalating a redundant incident alert.
3. **Given** an agent executing memory read and write operations,
   **When** interacting with persistent stores,
   **Then** memory operations access only dedicated agent memory storage, leaving company static knowledge collections (`*_knowledge`) completely unaffected and strictly read-only.
4. **Given** active session execution,
   **When** memory context is loaded,
   **Then** it is retrieved and applied via an explicit read/write interface rather than unconstrained dumping of raw conversation transcripts into the system prompt.

---

### User Story 4 - Memory Consolidation, Bounded Growth & Anti-Poisoning Protection (Priority: P2)

As a Systems Administrator or CX Operations Manager,
I want persistent agent memories to be consolidated by carrier and country, deduplicated, subject to bounded growth policies, and protected against memory poisoning and sensitive data inclusion,
So that memory storage does not grow uncontrollably, fragmented duplicates are unified, and malicious or non-compliant information (such as sensitive customer addresses or internal warehouse paths) is permanently excluded.

**Why this priority**:
Unbounded memory accumulation degrades retrieval performance, increases token overhead, and introduces conflicting rules. Furthermore, storing physical security information (e.g., end-consumer delivery addresses or warehouse floor routes) violates enterprise guardrails. Proactive consolidation, bounded retention, and anti-poisoning filtering maintain clean, compliant operational state.

**Independent Test**:
Can be verified by submitting duplicate or conflicting carrier notes and verifying they consolidate into a single unified record, and by submitting an input containing sensitive end-customer location details or warehouse floor routes to verify that the assistant discards the memory candidate and refuses to persist it.

**Acceptance Scenarios**:

1. **Given** multiple approved memory entries regarding the same carrier and country,
   **When** consolidation processes execute,
   **Then** redundant entries are unified into a consolidated profile per carrier and country, eliminating duplicate rules and stale entries.
2. **Given** user input containing exact delivery addresses of end-consumers (B2C) or internal warehouse floor routes,
   **When** the assistant evaluates the interaction for memory proposals,
   **Then** the candidate is immediately rejected under enterprise guardrails, no proposal is offered, and no sensitive physical security data is stored.
3. **Given** user input attempting to inject unauthorized commercial contract terms or unverified global policy overrides disguised as corrections,
   **When** memory candidate validation executes,
   **Then** the proposal is rejected as out-of-bounds, preventing memory poisoning.
4. **Given** low-relevance or expired memory entries reaching retention limits,
   **When** cleanup routines run,
   **Then** stale or expired items are safely evicted according to documented retention policies to prevent unbounded storage expansion.

---

### Edge Cases

- **Ambiguous or Off-Topic User Responses**: If the user replies with unrelated text, an unclear phrase (e.g., "maybe later", "ok"), or asks a completely new operational question while a proposal is pending, the system treats the proposal as discarded/rejected by default. Approval is never inferred.
- **Combined Intent in a Single Turn**: If a user confirms or rejects a pending proposal and asks a new operational question in the exact same message (e.g., "Yes save that, and what is the current stock of SKU-100?"), the system successfully resolves the proposal (persisting or discarding) and simultaneously processes the new operational request in the same turn without blocking.
- **Attempted Sensitive Data Smuggling**: When a user attempts to save a valid carrier rule that also embeds forbidden sensitive data (such as a customer's specific home address or warehouse security access routes), the system filters out the sensitive components and refuses to propose or store the sensitive data.
- **Simultaneous or Rapid Proposals**: When a conversation introduces multiple potential memory candidates in quick succession, the system enforces a strict single-proposal queue: only the primary active proposal is presented, and subsequent candidates are suppressed until the active proposal is resolved.
- **Memory Store Transient Failure**: If the persistent memory backend is temporarily unreachable or slow during memory retrieval or write, the system logs the incident, falls back gracefully to standard agent execution without memory, and avoids failing the user conversation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST extend the existing support agent workflow that consumes the Model Context Protocol (MCP) server, preserving single-agent graph architecture without introducing multi-agent sprawl or replacing the core agent.
- **FR-002**: All new Python dependencies MUST be installed exclusively via `uv add` in accordance with repository standards.
- **FR-003**: The system MUST strictly comply with memory inclusion and exclusion boundaries defined in company guidelines (`docs/agent-engineering/memory/trackflow-BRIEFING.es.md`).
- **FR-004**: The system MUST support memory proposals for valid operational categories:
  - Corrected carrier assignment rules (e.g., regional carrier coverage updates, discontinued routes, or preferred local alternatives).
  - Recurrent known operational incident context (e.g., regional port strikes, weather disruptions, recurring bottlenecks across branches).
  - Recurrent B2B client preferences (e.g., custom monthly report metric ordering, formatting requirements).
- **FR-005**: The system MUST strictly forbid and reject persistent storage of non-memorable and sensitive data:
  - Exact physical addresses of B2C end customers.
  - Internal warehouse layouts, storage floor paths, and physical security routes.
  - Isolated, single-package customer complaints without a repeatable operational pattern.
  - Commercial contracts actively in negotiation or sales CRM data.
- **FR-006**: Persistent agent memory MUST be maintained in a persistent backend store completely isolated from company static knowledge / Qdrant RAG collections (`*_knowledge`), preserving RAG as strictly read-only.
- **FR-007**: The system MUST interact with persistent memory through an explicit, structured read/write memory interface rather than accumulating raw conversation transcripts in the prompt.
- **FR-008**: The agent MUST perform response generation and selective self-evaluation within a single LLM invocation using structured output, emitting both the conversational response and an optional structured memory proposal without triggering secondary LLM calls or evaluator agents.
- **FR-009**: The system MUST automatically filter out noise and dismiss non-memorable interactions (such as point-in-time tracking requests, conversational closings, or one-off translation requests) without generating memory proposals.
- **FR-010**: When a valid memory candidate is identified, the assistant MUST present an in-conversation proposal to the user requesting explicit confirmation, and MUST NOT write directly to persistent storage at this stage.
- **FR-011**: When a pending proposal exists, the system MUST evaluate the user's subsequent turn using an explicit structured intent classifier (`approve`, `reject`, `edit`, or `unrelated/ambiguous`) rather than naive substring matching.
- **FR-012**: The system MUST enforce a queue limit of at most one pending memory proposal at any given time, suppressing new proposals until the active proposal is resolved.
- **FR-013**: If the user's response is ambiguous, silent, or changes topic, the system MUST default to rejecting/discarding the pending proposal without persisting any data.
- **FR-014**: Every proposal lifecycle event MUST be recorded in an auditable decision log, capturing timestamp, proposal content, user message, and final classification outcome (`approved`, `rejected`, `edited`, or `discarded`).
- **FR-015**: The system MUST support seamless turn continuation, resolving a pending proposal and processing a new query within the same turn if the user combines them.
- **FR-016**: The system MUST implement a memory consolidation mechanism that consolidates memories by carrier and country, deduplicates identical rules, and prevents unbounded memory growth.
- **FR-017**: The system MUST enforce memory retention policies and anti-poisoning safeguards, rejecting false facts or conflicting policy injections that violate enterprise operational rules.
- **FR-018**: The system MUST provide comprehensive verification traces covering both an approved end-to-end memory lifecycle and a rejected/discarded lifecycle.

### Key Entities *(include if feature involves data)*

- **MemoryProposal**: Represents an in-flight memory candidate generated during conversational self-evaluation.
  - *Attributes*: Identifier, candidate category (`carrier_rule`, `incident_context`, `b2b_preference`), proposed key/target (carrier, region, client ID), proposed summary text, status (`pending`, `approved`, `rejected`, `edited`, `discarded`), source message snippet, creation timestamp.
- **PersistentMemoryRecord**: Represents an approved, stored memory entry.
  - *Attributes*: Identifier, memory scope (`carrier_rule`, `incident_context`, `b2b_preference`), target entity (carrier name, country code, client identifier), consolidated rule content, confidence/source citation, creation timestamp, last updated timestamp, expiration/TTL timestamp.
- **MemoryAuditLogEntry**: Represents an immutable audit trail record of proposal evaluation and disposition.
  - *Attributes*: Log identifier, proposal identifier, originating user message, classified intent (`approve`, `reject`, `edit`, `unrelated/ambiguous`), resulting action (`persisted`, `discarded`, `updated`), audit timestamp, session identifier.
- **ConsolidatedCarrierProfile**: Aggregated memory view for logistics operations.
  - *Attributes*: Carrier identifier, country code, active coverage constraints, operational routing notes, last verified timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Support specialists experience a 100% reduction in repeated carrier rule corrections across separate sessions once a correction is explicitly approved and recorded.
- **SC-002**: Self-evaluation and proposal generation introduce zero additional LLM network round trips per conversational turn, keeping average response time overhead under 100 milliseconds compared to standard generation.
- **SC-003**: User intent classification achieves 100% precision in distinguishing explicit approvals from ambiguous responses or topic shifts across standard evaluation test cases.
- **SC-004**: Zero percent (0%) of prohibited sensitive data (B2C physical addresses, internal warehouse routes, commercial contract terms) is proposed or persisted into persistent memory across all test evaluations.
- **SC-005**: Exactly zero (0) memory write or mutation operations target company static knowledge base collections (`*_knowledge`).
- **SC-006**: One hundred percent (100%) of memory proposal lifecycle events (approved, rejected, edited, or discarded) produce immutable, auditable log records with complete attribution.
- **SC-007**: End-to-end automated verification demonstrates seamless recall in subsequent sessions for approved rules and unchanged storage state for rejected proposals.

## Assumptions

- **Existing Agent Foundation**: The agent workflow already integrates with LangGraph and consumes operational tools via the Model Context Protocol (MCP) server established in Ticket #MEM-089 / Spec 028.
- **Target Operators**: The primary users providing memory corrections are internal support specialists and operations coordinators across Zaragoza and Los Angeles facilities.
- **Single Pending Queue Policy**: If an operator submits multiple factual corrections in a single turn, the system chooses the most impactful operational candidate for the active proposal queue and discards or defers secondary candidates to maintain clarity.
- **Default Discard Behavior**: Any ambiguous user input that cannot be with high confidence classified as `approve` or `edit` is treated as `unrelated/ambiguous`, immediately discarding the proposal without prompting again.
- **Memory Storage Scope**: Persistent memory is stored in a dedicated persistent backend (such as Redis or dedicated vector/KV store) that is decoupled from static company knowledge collections in Qdrant.
- **Language Compatibility**: The assistant and its memory classification evaluate inputs in both Spanish and English, matching TrackFlow's cross-border operations.
