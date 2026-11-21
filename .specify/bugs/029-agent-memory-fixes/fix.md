# Bug Fix: Agent Memory Pre-Merge Fixes & AC Alignment (029)

- **Slug**: 029-agent-memory-fixes
- **Fixed**: 2026-11-21
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Resolved all pre-merge defects in the Agent Memory & Self-Improvement workflow (`029-agent-memory-self-improvement`): separated per-turn `trace_id` from conversation `thread_id` in `SupportAgentService.query()`, restricted `UserIntentClassifier.classify()` from treating 12+ character non-question ambiguous remarks as operational `residual_query` requests, enforced lazy TTL expiration (`expires_at <= now`) on pending `MemoryProposal` items with immutable `"discarded"` audit logging, and wired single-call structured LLM candidate output (`answer` + `memory_proposal`/`memory_candidate`) into `generation_node` and `evaluate_turn_for_proposal` with deterministic regex extraction fallback (documented in `research.md`).

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/support_agent_service.py` | modified | Always generate a unique `trace_id = str(uuid.uuid4())` per query call while setting `thread_id = request.thread_id.strip() if request.thread_id and request.thread_id.strip() else trace_id` for `initial_state["thread_id"]`, `run_config`, and `get_checkpoints(thread_id)`. |
| `services/api/application/services/memory_service.py` | modified | Added `_is_operational_query` to `UserIntentClassifier` to prevent non-question hesitation remarks from becoming `residual_query`; added `_expire_pending_if_needed` across `get_pending_proposal`, `get_proposal_by_id`, `evaluate_turn_for_proposal`, `resolve_pending_proposal`, and `apply_explicit_feedback`; added `_build_proposal_from_llm_candidate` and `llm_candidate` parameter to `evaluate_turn_for_proposal`. |
| `services/api/application/services/agent_workflow.py` | modified | Added `_parse_structured_llm_output` in `generation_node` to unpack single-call structured JSON/dict output (`answer` + `memory_proposal`/`memory_candidate`), route pure proposal discard turns directly from `intake` to `generation`, and pass `llm_candidate` to `evaluate_turn_for_proposal`. |
| `specs/029-agent-memory-self-improvement/research.md` | modified | Documented the single-call structured LLM output schema (`answer` + `memory_proposal`/`memory_candidate`) and deterministic `extract_memory_candidate` fallback in Section 2. |
| `services/api/tests/unit/test_memory_proposal_extractor.py` | modified | Added unit tests for single-call structured LLM output proposal creation and expired pending proposal auto-discard/thread unblocking. |
| `services/api/tests/unit/test_intent_classification.py` | modified | Split `unrelated_or_ambiguous` tests into `test_ambiguous_non_questions_classify_as_unrelated_with_no_residual_query` (`residual_query is None`) and `test_operational_topic_shifts_classify_as_unrelated_with_residual_query`. |
| `services/api/tests/unit/test_agent_workflow.py` | modified | Updated `test_t035_support_agent_service_records_multi_source_trace_and_checkpoints` to verify distinct `trace_id` and `thread_id` preservation. |
| `services/api/tests/integration/test_agent_memory_lifecycle.py` | modified | Verified distinct `trace_id` across multi-turn proposal creation/approval on a shared `thread_id` and added `test_ambiguous_non_question_remark_discards_proposal_without_false_positive_residual_query`. |

## Diff Highlights (optional)

```python
# services/api/application/services/support_agent_service.py
trace_id = str(uuid.uuid4())
thread_id = (
    request.thread_id.strip()
    if request.thread_id and request.thread_id.strip()
    else trace_id
)
initial_state: AgentState = {
    "query": request.query,
    "thread_id": thread_id,
    ...
    "trace_id": trace_id,
}
run_config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}
```

```python
# services/api/application/services/memory_service.py
def _expire_pending_if_needed(
    self,
    thread_id: str,
    now: Optional[datetime] = None,
) -> bool:
    proposal = self._pending_by_thread.get(thread_id)
    if proposal is None or proposal.status != "pending":
        return False
    effective_now = now or datetime.now(timezone.utc)
    if proposal.expires_at is not None and proposal.expires_at <= effective_now:
        expired_proposal = MemoryProposal(..., status="discarded", ...)
        self._proposals_by_id[proposal.proposal_id] = expired_proposal
        self._pending_by_thread.pop(thread_id, None)
        self._audit_repo.record_entry(
            MemoryAuditLogEntry(
                ...,
                event_type="discarded",
                resulting_action="proposal_discarded",
                details={"reason": "proposal_expired"},
            )
        )
        return True
    return False
```

## Tests Added or Updated

- `services/api/tests/unit/test_memory_proposal_extractor.py::TestMemoryProposalExtractor::test_single_call_structured_llm_output_creates_proposal_with_deterministic_fallback` — verifies single-call structured JSON LLM output (`answer` + `memory_proposal`) creates a guardrail-validated `MemoryProposal` and cleans the answer text.
- `services/api/tests/unit/test_memory_proposal_extractor.py::TestMemoryProposalExtractor::test_expired_pending_proposal_is_auto_discarded_and_unblocks_thread` — verifies expired pending proposals (`expires_at <= now`) transition to `"discarded"`, emit an immutable audit log entry (`reason="proposal_expired"`), and unblock the thread for new proposals.
- `services/api/tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_ambiguous_non_questions_classify_as_unrelated_with_no_residual_query` — pins down that 12+ character non-question hesitation remarks set `residual_query=None`.
- `services/api/tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_operational_topic_shifts_classify_as_unrelated_with_residual_query` — pins down that genuine operational inquiries on topic shifts populate `residual_query`.
- `services/api/tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_ambiguous_non_question_remark_discards_proposal_without_false_positive_residual_query` — verifies end-to-end that a 12+ character non-question ambiguous remark discards the pending proposal and completes with `sources_consulted == []`.
- `services/api/tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_approve_and_cross_session_recall` — verifies multi-turn proposal creation and approval share `thread_id` while recording distinct `trace_id` entries in `TraceRegistry`.

## Local Verification

- Commands run: `.venv/Scripts/python.exe -m pytest tests/unit/test_memory_proposal_extractor.py tests/unit/test_intent_classification.py tests/unit/test_memory_guardrails.py tests/unit/test_memory_consolidation.py tests/unit/test_agent_workflow.py tests/contract/test_memory_audit_log.py tests/integration/test_agent_memory_lifecycle.py tests/integration/test_memory_storage_isolation.py -v` → **88 passed**
- Manual checks: Verified approved memory cross-session recall (`test_approve_and_cross_session_recall`), rejected/discarded/expired audit log records (`test_records_rejected_and_discarded_audit_trails`, `test_expired_pending_proposal_is_auto_discarded_and_unblocks_thread`), and 0 Qdrant write operations across 10 proposal lifecycles (`test_zero_qdrant_writes_across_10_memory_proposal_lifecycles`).

## Deviations from Assessment

- In addition to the files listed in the assessment, `route_after_intake` in `services/api/application/services/agent_workflow.py` was updated to route pure proposal resolution turns (where `proposal_resolution` is present and `residual_query` is `None` with `selected_sources == []`) directly to `generation` rather than `retrieval`, ensuring pure discard/approval turns do not perform unnecessary vector searches.
- The assessment listed `services/api/tests/unit/test_memory_extraction.py` and `services/api/tests/unit/test_memory_intent_classifier.py`; in the repository these files are named `services/api/tests/unit/test_memory_proposal_extractor.py` and `services/api/tests/unit/test_intent_classification.py`, which were updated accordingly.

## Follow-ups

- Run `/speckit-bug-test slug=029-agent-memory-fixes` to record the verification report and complete any final branch merge steps.
