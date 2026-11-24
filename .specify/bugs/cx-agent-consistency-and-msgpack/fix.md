# Bug Fix: CX Agent Incident Discrepancy Handling, Chunk Synthesis Precision, Refusal Locale Detection, Redirect Taxonomy, and LangGraph Msgpack Serialization

- **Slug**: cx-agent-consistency-and-msgpack
- **Fixed**: 2026-11-24
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Resolved the four functional and consistency findings from the 20-query CX Agent evaluation suite: added delivery status discrepancy clarification (`in_progress` vs. user-reported delivered/missing) and a 3-step incident registration procedure in `_format_ticket_records_summary`, expanded `_ENGLISH_INDICATOR_PATTERN` so English imperative jailbreak prompts (`DEVELOPER_DEBUG_MODE`) in Spanish sessions receive English refusals, gated same-document secondary chunk synthesis by sub-topic relevance and distinguished greeting vs. conceptual logistics trivia metadata, and registered all `AgentState` domain dataclasses in LangGraph's `JsonPlusSerializer(allowed_msgpack_modules=...)`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Expanded `_ENGLISH_INDICATOR_PATTERN` with imperative/security tokens and added `sub_category` (`casual_greeting` vs `general_logistics_trivia`) and `sub_reason_code` metadata on casual redirects |
| `services/api/application/services/agent_workflow.py` | modified | Added `ALLOWED_CHECKPOINT_MSGPACK_MODULES` and `build_agent_checkpoint_serializer()`, wired `MemorySaver(serde=...)`, and enhanced `_format_ticket_records_summary` with delivery discrepancy clarification and 3-step incident opening procedure in ES/EN |
| `services/api/application/services/support_agent_service.py` | modified | Configured default `MemorySaver` with `serde=build_agent_checkpoint_serializer()` |
| `services/api/infrastructure/adapters/grounded_generation_adapter.py` | modified | Replaced blanket `0.12` same-document secondary chunk inclusion with sub-topic keyword gating for `returns-policy`, `sla-delivery`, `storage-pricing`, and `carrier-coverage` |
| `services/api/application/services/guardrail_cli.py` | modified | Removed `Deserializing unregistered type` warning suppression and surfaced `sub_category` in CLI guardrail intervention output |
| `services/api/tests/unit/test_agent_guardrails_input.py` | added test | Added unit test for English `DEVELOPER_DEBUG_MODE` jailbreak in an `es` session and verified `sub_category` / `sub_reason_code` metadata on greetings vs. logistics trivia |
| `services/api/tests/unit/test_guardrail_cli.py` | added test | Added regression assertions for concise chunk synthesis (#3, #4), order `#10492` delivered-vs-in-progress discrepancy and 3-step procedure (#5), and English refusal on `DEVELOPER_DEBUG_MODE` (#16) |
| `services/api/tests/unit/test_agent_workflow.py` | added test | Added unit test verifying `MemorySaver` with `build_agent_checkpoint_serializer()` emits zero unregistered msgpack type warnings |

## Diff Highlights (optional)

```python
ALLOWED_CHECKPOINT_MSGPACK_MODULES: Tuple[Tuple[str, str], ...] = (
    ("domain.agent.entities", "TicketToolInput"),
    ("domain.agent.entities", "TicketRecordDTO"),
    ("domain.agent.entities", "TicketToolOutput"),
    ("domain.agent.entities", "InventoryToolInput"),
    ("domain.agent.entities", "InventoryRecordDTO"),
    ("domain.agent.entities", "InventoryToolOutput"),
    ("domain.agent.entities", "AuthenticatedSessionContext"),
    ("domain.agent.entities", "GuardrailAuditEvent"),
    ("domain.agent.entities", "GuardrailEvaluationResult"),
    ("domain.agent.entities", "MemoryProposal"),
    ("domain.knowledge.entities", "KnowledgeChunk"),
    ("domain.knowledge.entities", "RetrievedContext"),
    ("domain.knowledge.entities", "SourceCitation"),
)


def build_agent_checkpoint_serializer() -> JsonPlusSerializer:
    """Return a JsonPlusSerializer configured with the explicit allowlist of TrackFlow AgentState domain entities."""
    return JsonPlusSerializer(
        allowed_msgpack_modules=list(ALLOWED_CHECKPOINT_MSGPACK_MODULES)
    )
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestJailbreakAndInstructionOverrides::test_english_developer_debug_mode_jailbreak_in_spanish_session_returns_english_refusal` — Verifies that an English `DEVELOPER_DEBUG_MODE` jailbreak prompt evaluated inside a `language="es"` session returns `JAILBREAK_REFUSAL_EN`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_personal_task_or_casual_trivia_redirects_casual_and_general_logistics_trivia` — Verifies that `CASUAL_TRIVIA_MANDATORY_REDIRECT` distinguishes `casual_greeting` (`CASUAL_GREETING_MANDATORY_REDIRECT`) from `general_logistics_trivia` (`GENERAL_LOGISTICS_TRIVIA_REDIRECT`) in `metadata`.
- `services/api/tests/unit/test_guardrail_cli.py::TestGuardrailCli::test_functional_and_adversarial_regression_suite` — Pins down concise chunk synthesis on Tests #3 and #4, status discrepancy explanation + 3-step incident registration procedure on Test #5 (`#10492`), and English refusal on Test #16 (`DEVELOPER_DEBUG_MODE`).
- `services/api/tests/unit/test_agent_workflow.py::TestUserStory6TracingAndCheckpointing::test_checkpoint_serializer_handles_all_agent_state_domain_types_without_unregistered_warnings` — Verifies that checkpoint serialization/deserialization across multi-tool, RAG, and guardrail-blocked runs emits zero `Deserializing unregistered type` msgpack warnings.

## Local Verification

- Commands run: `uv --directory services/api run pytest tests/unit/test_agent_guardrails_input.py tests/unit/test_guardrail_cli.py tests/unit/test_agent_workflow.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_agent_guardrails_observability.py tests/integration/test_knowledge_routes.py -q` → `363 passed` with zero msgpack serialization warnings.
- Manual checks: Verified CLI single-shot queries for `#10492` incident discrepancy, `DEVELOPER_DEBUG_MODE` in `--lang es`, return window/shipping costs, and Standard vs. Express transit comparison.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=cx-agent-consistency-and-msgpack` to record the verification report.
