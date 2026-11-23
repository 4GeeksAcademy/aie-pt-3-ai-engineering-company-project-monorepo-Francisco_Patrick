# Bug Assessment: Agent Memory Pre-Merge Fixes & AC Alignment (029)

- **Slug**: 029-agent-memory-fixes
- **Created**: 2026-11-21
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> # Concrete Bugs & Fixes Required Before Merge
>
> 1. **Fix `thread_id` override in `SupportAgentService.query()` (`support_agent_service.py`)**
> * Currently: `"thread_id": trace_id` overwrites `request.thread_id` with a new UUID every call, breaking multi-turn proposal resolution across turns in `SupportAgentService.query()`.
> * Fix: Use `thread_id = request.thread_id or trace_id` in `initial_state` and `run_config`.
>
> 2. **Avoid treating non-question ambiguous text as `residual_query` (`memory_service.py`)**
> * In `UserIntentClassifier.classify()`, `unrelated_or_ambiguous` currently sets `residual_query = cleaned` whenever `len(cleaned) >= 12` and not in a short hardcoded tuple. Any 12+ character non-question ambiguous remark gets fed as `effective_query`.
> * Fix: Only populate `residual_query` on `unrelated_or_ambiguous` when the message is an actual query/request (or when explicitly separated), not arbitrary ambiguous commentary.
>
> 3. **Check proposal expiration (`expires_at`) (`memory_service.py`)**
> * `MemoryProposal` sets `expires_at = now + timedelta(minutes=15)`, but `get_pending_proposal` and `evaluate_turn_for_proposal` never check `proposal.expires_at`.
> * Fix: If `proposal.expires_at and proposal.expires_at <= datetime.now(timezone.utc)`, mark it `discarded`, log an audit entry, remove it from `_pending_by_thread`, and allow normal processing.
>
> 4. **Align single-call structured output with AC-3.2 (or document deterministic fallback)**
> * AC-3.2 calls for structured output in a single LLM call (`answer` + `memory_proposal`). Right now `generation_node` calls `rag_generate_answer` and then runs deterministic keyword/regex extraction in `evaluate_turn_for_proposal`. If structured LLM output is part of your intended design (as described in `research.md`), wire structured output into the LLM generation path with deterministic regex extraction as fallback when no LLM generator is used, and add a test for it.
>
> 5. **Deliver explicit evidence & merge to `main` (AC-6.1 / AC-6.3)**
> * Include concrete test/run evidence (approved recall + rejected/discarded audit records) and merge the PR into `main` once the fixes above are applied.

## Symptom

1. **Conflated `trace_id` and `thread_id` in `SupportAgentService.query()`**: `trace_id` is currently derived from `request.thread_id` (`support_agent_service.py:198-202`) and passed as both `"thread_id": trace_id` and `"trace_id": trace_id`, rather than generating a unique `trace_id = str(uuid.uuid4())` per query execution and resolving `thread_id = request.thread_id.strip() if request.thread_id and request.thread_id.strip() else trace_id` for `initial_state["thread_id"]`, `run_config`, and checkpoint lookup. When multiple turns share a `request.thread_id`, reusing `trace_id = thread_id` causes trace collisions in `TraceRegistry`, or if `trace_id` is generated fresh per call without separating `thread_id`, multi-turn proposal state is lost.
2. **False-positive `residual_query` on ambiguous non-questions**: In `UserIntentClassifier.classify()` (`memory_service.py:343-354`), any `unrelated_or_ambiguous` input with `len(cleaned) >= 12` not matching 4 hardcoded strings (`"maybe later"`, `"hmm not sure"`, `"not sure"`, `"i guess"`) populates `residual_query = cleaned`. Consequently, non-question ambiguous remarks (e.g., `"let me think about that for a moment"`, `"I will ask my supervisor first"`) are treated as operational queries in `intake_node` and routed into RAG/tool execution instead of completing as pure proposal discard turns.
3. **Unenforced `MemoryProposal.expires_at` TTL**: `MemoryProposal` sets a 15-minute `expires_at` timestamp (`memory_service.py:229`, `627`, `847`), but `get_pending_proposal`, `evaluate_turn_for_proposal`, `resolve_pending_proposal`, and `apply_explicit_feedback` never inspect `proposal.expires_at`. An expired pending proposal blocks new proposals on the thread (FR-012) and can still be approved after expiration.
4. **Missing single-call structured LLM candidate extraction path (AC-3.2)**: `generation_node` (`agent_workflow.py:1028-1071`) invokes `rag_generate_answer` (which only returns text) and then relies solely on deterministic regex extraction in `evaluate_turn_for_proposal`, without wiring structured single-call LLM output (`answer` + optional `memory_candidate`/`memory_proposal`) with deterministic regex extraction as a fallback when no structured LLM candidate is produced.
5. **Pre-merge evidence & branch integration (AC-6.1 / AC-6.3)**: Explicit execution evidence of approved memory recall and rejected/discarded audit records must be captured and verified before merging `feature/agent-memory` into `main`.

## Reproduction

1. **Multi-turn `thread_id` / `trace_id` collision**: Call `SupportAgentService.query(AgentQueryRequest(query="...", thread_id="session-1"))` across two turns. Observe that `trace_id` is overwritten with `"session-1"` on both turns (colliding in `TraceRegistry`) because `thread_id` and `trace_id` are not separated into a unique per-call `trace_id` and a persistent `thread_id = request.thread_id or trace_id`.
2. **Ambiguous non-question treated as `residual_query`**: Call `UserIntentClassifier().classify("I need to think about whether to save that", "SEUR no longer covers rural Zaragoza")`. Observe `intent == "unrelated_or_ambiguous"` with `residual_query == "I need to think about whether to save that"`, causing `intake_node` to route the remark to RAG retrieval instead of a pure discard acknowledgment.
3. **Expired proposal remains active**: Create a pending proposal in `AgentMemoryService`, set its `expires_at` in the past (`now - timedelta(minutes=1)`), and call `get_pending_proposal(thread_id)` or `evaluate_turn_for_proposal(...)`. Observe the expired proposal is still returned as `"pending"` and blocks new proposals on that thread.
4. **Structured LLM output ignored in `generation_node`**: Provide an `llm_generator` that returns a structured JSON/dict response containing `{"answer": "...", "memory_proposal": {...}}` (or implements structured single-call generation). Observe `generation_node` treats the raw response as plain text and only runs regex extraction in `evaluate_turn_for_proposal`.

## Suspected Code Paths

- `services/api/application/services/support_agent_service.py:198-237,286` — `SupportAgentService.query()` conflates `trace_id` and `thread_id` instead of generating a unique `trace_id = str(uuid.uuid4())` and setting `thread_id = request.thread_id.strip() if request.thread_id and request.thread_id.strip() else trace_id` for `initial_state["thread_id"]`, `run_config`, and `get_checkpoints(thread_id)`.
- `services/api/application/services/memory_service.py:341-355` — `UserIntentClassifier.classify()` sets `is_operational_question = len(cleaned) >= 12 and cleaned.lower() not in (...)`, populating `residual_query` for arbitrary non-question remarks.
- `services/api/application/services/memory_service.py:408-484,485-505,749-768` — `AgentMemoryService.get_pending_proposal()`, `evaluate_turn_for_proposal()`, `resolve_pending_proposal()`, and `apply_explicit_feedback()` do not check `proposal.expires_at <= datetime.now(timezone.utc)`.
- `services/api/application/services/agent_workflow.py:957-1072` & `services/api/application/services/memory_service.py:423-484` — `generation_node()` and `evaluate_turn_for_proposal()` do not extract or pass structured single-call LLM `memory_proposal` / `memory_candidate` output before falling back to deterministic regex extraction (`extract_memory_candidate`).

## Root Cause Hypothesis

High confidence. First, `SupportAgentService.query()` assigned `trace_id` directly from `request.thread_id` rather than maintaining distinct `trace_id` (unique per invocation) and `thread_id = request.thread_id or trace_id` (persistent across turns in a conversation). Second, `UserIntentClassifier.classify()` used a simplistic length heuristic (`len(cleaned) >= 12`) to detect whether an `unrelated_or_ambiguous` reply was a new operational query, which misclassifies declarative hesitation or commentary as a residual query. Third, while `MemoryProposal` was designed with a 15-minute `expires_at` window, lazy expiration eviction in `AgentMemoryService` was only implemented for persisted `PersistentMemoryRecord` items (`evict_expired_memories`), not for in-memory pending proposals in `_pending_by_thread`. Fourth, `generation_node` delegated answer synthesis to `rag_generate_answer` and candidate detection exclusively to deterministic `extract_memory_candidate`, omitting the single-call structured LLM output parsing (`answer` + `memory_proposal` / `memory_candidate`) with deterministic fallback described in `research.md` and AC-3.2.

## Proposed Remediation

**Preferred**:
1. **Separate `thread_id` and `trace_id` in `SupportAgentService.query()` (`support_agent_service.py`)**:
   - Always generate a unique `trace_id = str(uuid.uuid4())` per query execution.
   - Compute `thread_id = request.thread_id.strip() if request.thread_id and request.thread_id.strip() else trace_id`.
   - Pass `"thread_id": thread_id` and `"trace_id": trace_id` in `initial_state`, use `{"configurable": {"thread_id": thread_id}}` in `run_config`, and pass `thread_id` to `self.get_checkpoints(thread_id)`.
2. **Restrict `residual_query` in `UserIntentClassifier.classify()` (`memory_service.py`)**:
   - Add an explicit operational query detector `_is_operational_query(text: str) -> bool` that checks whether an `unrelated_or_ambiguous` message is an actual operational question or request (e.g., contains `?`, starts with an interrogative/request verb like `what`, `where`, `when`, `how`, `who`, `which`, `can you`, `could you`, `please check`, `check`, `show`, `list`, `lookup`, `tell me`, or references operational domain entities/metrics such as `sku`, `stock`, `inventory`, `ticket`, `incident`, `inc-`, `sla`, `return`, `policy`, `storage`, `delivery`, `refund`, `discount`, `warehouse`, while explicitly excluding hesitation/commentary phrases like `"let me think..."`, `"i'll ask my supervisor..."`, `"not right now..."`, `"maybe later..."`).
   - Only populate `residual_query = cleaned` on `unrelated_or_ambiguous` when `_is_operational_query(cleaned)` is `True`.
3. **Enforce `proposal.expires_at` across `AgentMemoryService` (`memory_service.py`)**:
   - Implement a thread-safe helper `_expire_pending_if_needed(self, thread_id: str, now: Optional[datetime] = None) -> bool` (and check inside `get_pending_proposal`, `evaluate_turn_for_proposal`, `resolve_pending_proposal`, and `apply_explicit_feedback`).
   - When `proposal.expires_at is not None and proposal.expires_at <= now`, update the proposal status to `"discarded"`, store the updated `MemoryProposal` in `self._proposals_by_id`, remove it from `self._pending_by_thread`, and record a `MemoryAuditLogEntry` with `event_type="discarded"`, `resulting_action="proposal_discarded"`, and `details={"reason": "proposal_expired"}`.
4. **Wire single-call structured LLM output with deterministic fallback (`agent_workflow.py` & `memory_service.py` & `research.md`)**:
   - Allow `generation_node` / `LLMGenerationPort` to return or parse structured single-call output (either via an optional `generate_structured_response` method on `LLMGenerationPort` or by parsing structured JSON `{"answer": ..., "memory_proposal": ...}` / `{"answer": ..., "memory_candidate": ...}` returned by `llm_generator.generate_grounded_answer` in a single LLM call).
   - Pass any structured `llm_candidate` into `memory_service.evaluate_turn_for_proposal(..., llm_candidate=...)`, which validates it through `MemoryGuardrailValidator` and constructs the `MemoryProposal` (or falls back deterministically to `extract_memory_candidate` when no structured LLM candidate is provided).
   - Document the single-call structured output and deterministic fallback behavior in `specs/029-agent-memory-self-improvement/research.md`.
5. **Verification Evidence & Merge (AC-6.1 / AC-6.3)**:
   - Run the unit and integration test suites to capture concrete verification evidence of approved cross-session recall and rejected/discarded audit log records, and merge `feature/agent-memory` into `main` once all checks pass.

**Files likely to change**:
- `services/api/application/services/support_agent_service.py`
- `services/api/application/services/memory_service.py`
- `services/api/application/services/agent_workflow.py`
- `specs/029-agent-memory-self-improvement/research.md`
- `services/api/tests/unit/test_memory_extraction.py`
- `services/api/tests/unit/test_memory_intent_classifier.py`
- `services/api/tests/integration/test_agent_memory_lifecycle.py`

**Tests to add or update**:
- Unit test verifying `SupportAgentService.query()` preserves `request.thread_id` across multi-turn proposal creation and resolution while assigning unique `trace_id` values per turn.
- Unit test verifying `UserIntentClassifier.classify()` sets `residual_query=None` for 12+ character non-question ambiguous commentary (e.g. `"Let me think about that for a moment"`, `"I will check with my supervisor first"`) while still extracting `residual_query` for genuine operational questions (e.g. `"Can you check current stock for SKU-401?"`).
- Unit/integration test verifying that an expired `MemoryProposal` (`expires_at <= now`) is automatically marked `"discarded"`, removed from `_pending_by_thread`, logged in the audit repository, and allows a new proposal to be created on the same thread.
- Unit test verifying single-call structured LLM generation output (`answer` + `memory_proposal`/`memory_candidate`) in `generation_node` creates a guardrail-validated `MemoryProposal` in a single LLM call and falls back to deterministic regex extraction when plain text is returned.

## Risks & Considerations

- **Backward Compatibility with Existing Trace & Checkpoint Tests**: Any test passing `request.thread_id` and inspecting `result.trace_id` or `service.get_checkpoints(...)` must be checked to ensure separating `thread_id` and `trace_id` (or keeping `thread_id = request.thread_id or trace_id`) does not break existing `test_support_agent_*.py` assertions.
- **Guardrail Enforcement on Structured LLM Candidates**: Any memory candidate produced via structured LLM output must still pass `MemoryGuardrailValidator.validate_candidate()` and PII masking (`mask_sensitive_pii`) before becoming a pending `MemoryProposal`.

## Open Questions

- None — all five items have clear root causes and deterministic remediation paths.
