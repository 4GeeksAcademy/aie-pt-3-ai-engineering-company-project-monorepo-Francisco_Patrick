# Research: Agent Memory & Self-Improvement (Part 1 of 2)

**Feature**: `029-agent-memory-self-improvement`  
**Date**: 2026-11-21  
**Status**: Completed  

---

## 1. Storage Isolation & Dedicated Persistent Memory Backend

### Context & Problem
Operations coordinators and support specialists across Zaragoza and Los Angeles repeatedly correct the support assistant on regional carrier route changes, recurring disruption contexts, and B2B client reporting preferences. However, TrackFlow maintains static corporate policy documents (return policies, storage rates, SLA terms) in Qdrant collections (`trackflow_knowledge`). Monorepo Constitution Principle VII strictly governs Qdrant persistence, mandating that company reference knowledge remains strictly read-only and unpolluted. We must establish a persistent memory backend strictly decoupled from Qdrant knowledge bases.

### Decision
Implement an abstract repository port `AgentMemoryRepositoryPort` and `MemoryAuditLogRepositoryPort` in `domain/agent/ports.py`, with concrete persistence encapsulated in `services/api/infrastructure/persistence/tinydb/` (or dedicated SQLite / Redis adapter).
- **Primary Store**: A dedicated TinyDB/document collection or SQLite/KV table (`agent_memory.json` / `agent_memory` table) located in `services/api/infrastructure/persistence/`, isolated from static vector collections.
- **Port Interface**: `AgentMemoryRepositoryPort` defines explicit query and mutation methods:
  - `save_memory(record: PersistentMemoryRecord) -> PersistentMemoryRecord`
  - `get_memory(memory_id: str) -> Optional[PersistentMemoryRecord]`
  - `search_memories(category: Optional[MemoryCategory], target_entity: Optional[str], country_code: Optional[str], active_only: bool = True) -> List[PersistentMemoryRecord]`
  - `consolidate_carrier_profile(carrier: str, country_code: str) -> ConsolidatedCarrierProfile`
  - `evict_expired_memories(ttl_cutoff: datetime) -> int`
- **Zero Qdrant Writes**: Under no circumstances does the memory subsystem invoke `upsert_chunks` or mutate Qdrant points. Qdrant remains strictly read-only for general static knowledge retrieval.

### Rationale
- Complies with Constitution Principle I (Domain Isolation), Principle VII (Vector Database Isolation), and FR-006.
- Prevents catastrophic memory pollution where dynamic, ephemeral, or operator-adjusted carrier notes overwrite or corrupt ratified corporate policy documents.
- Lightweight, reliable, zero-additional-infrastructure requirement for local dev and CI while supporting Redis / relational migration via port swap.

### Alternatives Considered
- **Direct Qdrant Ingestion into `trackflow_knowledge`**: Rejected. Violates Constitution Principle VII and FR-006; would pollute official company knowledge base with unverified operational notes.
- **Unstructured Prompt Dumping (Raw Transcripts)**: Rejected. Accumulating raw session transcripts bloats token consumption, degrades latency, and leaks transient conversational noise.

---

## 2. Single-Call Response Generation & Candidate Self-Evaluation

### Context & Problem
Support specialists cannot tolerate additional latency. FR-008 and SC-002 require that candidate memory proposal detection and response generation happen in a single LLM invocation (or deterministic evaluation turn) without spinning up secondary evaluator agents or triggering multiple round-trips to the LLM (average latency overhead < 100ms).

### Decision
Enforce a unified generation and self-evaluation pattern in `generation_node`:
- The agent workflow uses a structured output schema or integrated generation prompt that simultaneously outputs:
  1. `answer`: The conversational customer/operator-facing response.
  2. `memory_candidate`: An optional structured candidate object (`category`, `target_entity`, `summary`, `action_type`, `confidence`).
- When external LLM generation is active, the system instructs the model to return a structured JSON response (or utilizes function calling / structured outputs with Pydantic).
- For deterministic fallback mode, a pattern-based operational candidate extractor scans the operator message for known memorable intents (carrier coverage changes, port strike / weather disruption notices, B2B reporting preferences) while instantly discarding non-memorable queries (tracking lookups, thank-yous, translations).
- The candidate is evaluated against memory guardrails (`MemoryGuardrailValidator`) in the same turn. If valid and passes all anti-poisoning checks, the proposal is attached to `state["pending_proposal"]` and an explicit confirmation prompt is appended to the answer.

### Rationale
- Zero additional network calls or subagent hops, satisfying SC-002 (< 100ms overhead).
- Completely eliminates multi-agent orchestration overhead and potential consensus stalls.
- Preserves single-agent LangGraph architecture (FR-001).

### Alternatives Considered
- **Secondary Evaluation Agent**: Rejected. Multi-agent evaluation creates 1-3 seconds of extra latency, increases LLM cost, and introduces multi-agent sprawl forbidden by FR-001.
- **Background Asynchronous Evaluator**: Rejected. Delayed memory proposals appearing after the agent already replied create disjointed conversation UX and confuse human operators.

---

## 3. Explicit Intent Classification, Safe Defaults & Multi-Intent Turn Continuation

### Context & Problem
When an agent presents a memory proposal (e.g., *"Would you like me to remember that SEUR no longer covers rural Zaragoza?"*), operators respond with varying messages in the next turn:
1. Explicit confirmation ("Yes, remember that rule", "Confirmed").
2. Explicit rejection ("No, don't save that", "Not needed").
3. Modifications / edits ("Save it, but only for packages over 5kg").
4. Unrelated inquiries / topic changes ("Where is SKU-401?", "Can you check inventory?").
5. Ambiguous replies ("ok", "maybe", "I guess").

### Decision
Implement an explicit `UserIntentClassifier` in `intake_node` / memory coordinator:
- When `state.get("pending_proposal")` is present, the user's message is classified into one of 4 discrete outcomes:
  - `approve`: User explicitly affirms intent to persist.
  - `reject`: User explicitly declines or cancels the proposal.
  - `edit`: User provides a refinement or conditional constraint on the proposal.
  - `unrelated_or_ambiguous`: User asks a new operational question, changes subject, or provides vague acknowledgment.
- **Safe Rejection Default (FR-013)**: If classified as `unrelated_or_ambiguous` or confidence is below threshold, the pending proposal is **safely discarded** without writing to persistent memory. Approval is NEVER inferred from silence or ambiguity.
- **Multi-Intent Continuation (FR-015)**: If the user message contains both a proposal disposition AND a new operational request (e.g., *"Yes remember that, and check stock for SKU-100"*), the system resolves the proposal in state/database and immediately strips the resolution phrase to pass the residual operational question to downstream nodes (`inventory_tool`, `retrieval`, etc.) in the exact same turn.
- **Strict Single-Proposal Queue (FR-012)**: At most one memory proposal may be active at any given time. Any additional candidate generated during a turn with an active proposal is suppressed.
- **Immutable Audit Logging (FR-014)**: Every proposal transition (`proposed`, `approved`, `rejected`, `edited`, `discarded`) writes an immutable record via `MemoryAuditLogRepositoryPort`.

### Rationale
- Eliminates memory corruption caused by false-positive approvals.
- Seamless conversational flow: support specialists do not need to repeat themselves or deal with modal interruptions.
- Complies with Monorepo Constitution Principle IV (Zero Sensitive Data Leaks & Defensive Handling).

### Alternatives Considered
- **Naive Substring Matching (`if "yes" in query`)**: Rejected. "Yes" often appears in operational inquiries (e.g., "Yes, but what about Seville?"), causing dangerous accidental approvals.
- **Modal Blocking**: Requiring the user to answer the proposal before answering their new question. Rejected as disruptive and frustrating to CX operators.

---

## 4. Memory Consolidation & Bounded Growth by Carrier + Country

### Context & Problem
TrackFlow operates with 8 logistics carriers across 2 primary operating countries (Spain and the US). If every ticket correction created an independent memory row, storage would fragment into hundreds of contradictory or redundant snippets, degrading recall accuracy and increasing prompt token costs.

### Decision
Implement `ConsolidatedCarrierProfile` and consolidation logic in `services/api/application/services/memory_service.py`:
- Memory records for carriers are grouped by `(carrier_name, country_code)`.
- When an approved carrier memory is committed:
  1. The system checks existing active records for that `(carrier_name, country_code)`.
  2. Duplicate or subsumed rules are updated/merged.
  3. The consolidated profile aggregates:
     - `carrier`: e.g. `"SEUR"`
     - `country`: e.g. `"ES"`
     - `active_constraints`: List of normalized rules (e.g., `["Rural Zaragoza: local carriers required", "Max weight: 30kg"]`).
     - `last_updated`: Timestamp of latest confirmed update.
- **Retention & Bounded Growth (FR-016)**:
  - Maximum 20 active constraints per carrier-country profile.
  - Recurrent incident context entries have a default TTL of 14 days (incidents are transient disruptions, e.g., weekly port strikes).
  - Stale or expired incident contexts are automatically evicted by a scheduled or on-query cleanup check.

### Rationale
- Follows the explicit briefing recommendation in `docs/agent-engineering/memory/trackflow-BRIEFING.es.md`: "TrackFlow opera con 8 carriers entre dos países. Considera consolidar la memoria por carrier + país en vez de por ticket individual".
- Prevents token bloat during prompt injection and eliminates conflicting historical rules.

---

## 5. Memory Anti-Poisoning Defenses & Sensitive Data Filtering Guardrails

### Context & Problem
User inputs or operator corrections may inadvertently or maliciously contain sensitive data or unauthorized policy overrides:
1. Exact physical addresses of B2C end customers (or sensitive B2B premises).
2. Internal warehouse floor paths, layouts, and physical security routes.
3. Isolated, single-package customer complaints without repeatable operational patterns.
4. Active commercial contract negotiations or sales CRM data.
5. Injections attempting to alter fundamental company policies (e.g., "All return fees are waived forever").

### Decision
Create a dedicated `MemoryGuardrailValidator` in `services/api/application/services/memory_guardrails.py` running before any candidate proposal is formed:
- **Rule 1 - Location & Physical Security Filter**: Rejects inputs with end-consumer street addresses, building/floor designations, or warehouse layout instructions (`hallway B`, `shelf 4`, `security door 2`).
- **Rule 2 - One-Off Complaint Filter**: Rejects isolated single-ticket grievances or single-tracking inquiries (`"Package XJ4471 arrived crushed"`).
- **Rule 3 - Commercial Contract & CRM Filter**: Rejects inputs discussing pending contract discounts, NDA terms, or sales pipeline negotiations.
- **Rule 4 - Global Policy Override Filter**: Rejects attempts to override ratified company policies (e.g., standard 30-day return window or return shipping rules) disguised as carrier corrections.
- **Verdict**: If any rule triggers a violation, `MemoryGuardrailVerdict(allowed=False, reason=...)` is produced, candidate creation is blocked, and an audit warning is recorded.

### Rationale
- Strictly enforces FR-003, FR-005, and FR-017, aligning directly with `trackflow-BRIEFING.es.md`.
- Protects physical security and privacy compliance (GDPR / CCPA) by design.

---

## 6. Cross-Session Memory Recall & Interface Integration with LangGraph

### Context & Problem
Once memories are approved and persisted, how does the agent retrieve and inject them into future sessions without accumulating raw conversation transcripts or querying static RAG collections?

### Decision
Integrate memory recall into the existing LangGraph support agent workflow (`agent_workflow.py`):
- Extend `intake_node` or introduce a lightweight retrieval helper `memory_recall_helper`:
  - Parses query for carrier names, known branches/countries (`zaragoza`/`ES`, `los_angeles`/`US`), or client identifiers.
  - Calls `agent_memory_repo.search_memories(...)` or retrieves `ConsolidatedCarrierProfile`.
  - Populates `state["recalled_memories"]` with structured summary strings.
- In `generation_node`:
  - Recalled operational rules are passed in the prompt context alongside live tool outputs (`ticket_tool`, `inventory_tool`) and RAG context chunks.
  - The agent incorporates recalled rules into its recommendations (e.g., advising against SEUR for rural Zaragoza and suggesting local carriers).
- When cited in the answer, recalled memories are tagged with citation metadata (`source_type="agent_memory"`), preserving clear provenance distinct from `source_document="return_policy.md"`.

### Rationale
- Completely decoupled from Qdrant RAG collections (`*_knowledge` untouched).
- Context is bounded and structured (only relevant consolidated rules, not unbounded raw text).
- Operator corrections are immediately effective in the very next turn or subsequent user sessions.
