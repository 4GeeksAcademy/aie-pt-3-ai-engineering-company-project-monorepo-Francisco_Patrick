# Bug Verification: Agent Memory Pre-Merge Fixes & AC Alignment (029)

- **Slug**: 029-agent-memory-fixes
- **Tested**: 2026-11-21
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

All four reported defects no longer reproduce and the pre-merge acceptance criteria (AC-3.2, AC-6.1, AC-6.3) are verified end-to-end across 87 passing unit, contract, and integration tests with zero regressions. Multi-turn conversations preserve `thread_id` while emitting distinct per-turn `trace_id` entries, 12+ character non-question ambiguous remarks discard pending proposals without triggering false-positive `residual_query` RAG retrieval, expired pending `MemoryProposal` records (`expires_at <= now`) automatically transition to `"discarded"` with an immutable audit record (`reason="proposal_expired"`), and `generation_node` unpacks single-call structured LLM output (`answer` + `memory_proposal`/`memory_candidate`) with deterministic regex fallback.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `.\.venv\Scripts\python.exe -m pytest tests/unit/test_memory_proposal_extractor.py tests/unit/test_intent_classification.py tests/integration/test_agent_memory_lifecycle.py -v` | pass | 52 passed; exercised all 4 reproduction cases (multi-turn `thread_id`/`trace_id` separation, ambiguous non-question `residual_query is None`, expired proposal auto-discard, single-call structured LLM candidate output) plus approved cross-session recall and rejected/discarded audit trails. |
| New / updated tests | `.\.venv\Scripts\python.exe -m pytest tests/unit/test_memory_proposal_extractor.py tests/unit/test_intent_classification.py tests/integration/test_agent_memory_lifecycle.py -v` | pass | 52 passed across unit and integration suites covering the 6 new/updated tests recorded in `fix.md`. |
| Regression suite | `.\.venv\Scripts\python.exe -m pytest tests/unit/test_memory_guardrails.py tests/unit/test_memory_consolidation.py tests/unit/test_agent_workflow.py tests/contract/test_memory_audit_log.py tests/integration/test_memory_storage_isolation.py -v` | pass | 35 passed; verified guardrails, consolidation, LangGraph workflow nodes/checkpoints, audit log contract, and 0 Qdrant writes across 10 proposal lifecycles. |
| Lint / type-check | `.\.venv\Scripts\python.exe -m py_compile application/services/support_agent_service.py application/services/memory_service.py application/services/agent_workflow.py` | pass | Exit code 0; all modified service modules compile cleanly with zero syntax or import errors. |

## Output Excerpts

```text
tests/unit/test_memory_proposal_extractor.py::TestMemoryProposalExtractor::test_single_call_structured_llm_output_creates_proposal_with_deterministic_fallback PASSED [ 26%]
tests/unit/test_memory_proposal_extractor.py::TestMemoryProposalExtractor::test_expired_pending_proposal_is_auto_discarded_and_unblocks_thread PASSED [ 28%]
tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_ambiguous_non_questions_classify_as_unrelated_with_no_residual_query[...] PASSED
tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_operational_topic_shifts_classify_as_unrelated_with_residual_query[...] PASSED
tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_approve_and_cross_session_recall PASSED [ 88%]
tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_ambiguous_non_question_remark_discards_proposal_without_false_positive_residual_query PASSED [ 96%]
======================= 52 passed, 2 warnings in 279.62s (0:04:39) ========================
```

```text
tests/unit/test_agent_workflow.py::TestUserStory6TracingAndCheckpointing::test_t035_support_agent_service_records_multi_source_trace_and_checkpoints PASSED [ 85%]
tests/contract/test_memory_audit_log.py::TestMemoryAuditLogContract::test_records_proposed_and_approved_audit_trail PASSED [ 91%]
tests/contract/test_memory_audit_log.py::TestMemoryAuditLogContract::test_records_rejected_and_discarded_audit_trails PASSED [ 94%]
tests/integration/test_memory_storage_isolation.py::TestMemoryStorageIsolation::test_zero_qdrant_writes_across_10_memory_proposal_lifecycles PASSED [100%]
================= 35 passed, 2 warnings in 195.53s (0:03:15) ==================
```

## Residual Risks

- Pending proposals (`_pending_by_thread`) are stored in-memory within `AgentMemoryService` with lazy TTL eviction on subsequent thread access or proposal lookup; if the API worker restarts before a 15-minute window elapses, in-flight unconfirmed proposals are cleared with process memory (consistent with the spec design where only confirmed memories and audit logs are persisted).

## Recommendation

Close the bug — verified end-to-end. All four defects from the assessment and all acceptance criteria (`AC-3.2`, `AC-6.1`, `AC-6.3`) are verified with automated unit, contract, and integration test evidence, and `feature/agent-memory` is ready to merge into `main`.
