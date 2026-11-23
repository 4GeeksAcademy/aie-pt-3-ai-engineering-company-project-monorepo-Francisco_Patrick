# Bug Fix: Memory Intent Classifier Confirmation and Instruction Boundary Fix

- **Slug**: memory-classifier-confirmation
- **Fixed**: 2026-11-21
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added dedicated brief confirmation and rejection exact match patterns (`_BRIEF_APPROVE_PATTERN` and `_BRIEF_REJECT_PATTERN`) to accept natural concise responses ("Yes", "Sí", "No", etc.), restricted `_APPROVE_PREFIX_PATTERN` to strictly require explicit rule/memory targets so compound task instructions like "Yes, remember to check the stock tomorrow" do not falsely approve pending proposals, and updated intake routing to allow short 2-character proposal resolution inputs.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/memory_service.py` | modified | Added `_BRIEF_APPROVE_PATTERN` and `_BRIEF_REJECT_PATTERN`; restricted `_APPROVE_PREFIX_PATTERN` to disallow `remember to ...` action directives; enhanced `_OPERATIONAL_QUERY_START_PATTERN` to recognize operational instructions preceded by affirmatives. |
| `services/api/application/services/agent_workflow.py` | modified | Updated `route_after_intake` to only refuse `< MIN_QUERY_LENGTH` inputs when no active `proposal_resolution` exists, allowing 2-character natural responses ("No", "Sí") to resolve pending proposals. |
| `services/api/tests/unit/test_intent_classification.py` | modified | Added parametrized tests for brief natural confirmations, brief natural rejections, and rejection of "yes + new instruction" compound queries. |
| `services/api/tests/integration/test_agent_memory_lifecycle.py` | modified | Added lifecycle integration tests verifying "Yes" persists rule across sessions, "No" discards rule and records `rejected` audit event, and "Yes, remember to check current stock..." safely discards proposal while answering the stock query. |

## Diff Highlights (optional)

```python
# services/api/application/services/memory_service.py
_BRIEF_APPROVE_PATTERN = re.compile(
    r"^\s*(?:yes|yeah|yep|s[ií]|claro|por\s+supuesto|confirm|confirmed|approve|approved)"
    r"(?:\s*,?\s*(?:please|por\s+favor))?[\s.!]*$",
    re.IGNORECASE,
)

_BRIEF_REJECT_PATTERN = re.compile(
    r"^\s*(?:no|nope|reject|rejected|discard|cancel)"
    r"(?:\s*,?\s*(?:thanks|gracias|please|por\s+favor))?[\s.!]*$",
    re.IGNORECASE,
)

# Reject 'remember to <action>' by requiring an explicit rule target or memory preposition
_APPROVE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:"
    r"(?:yes|yeah|yep|s[ií]|claro|por\s+supuesto)\s*,?\s*(?:please\s+|por\s+favor\s+)?"
    r"(?:"
    r"(?:remember|save|store|keep|confirm|approve)"
    r"(?!to\s+(?!memory\b))"
    r"(?:\s+(?:that|this|it|the\s+rule|the))(?:\s+rule)?(?:\s+for\s+[A-Za-z0-9_-]+)?"
    r"(?:\s+(?:to\s+memory|for\s+future\s+sessions|in\s+memory|\s+por\s+favor))?"
    ...
```

```python
# services/api/application/services/agent_workflow.py
query = (state.get("query") or "").strip()
proposal_resolution = state.get("proposal_resolution")
if (
    (len(query) < MIN_QUERY_LENGTH and proposal_resolution is None)
    or state.get("is_refusal") is True
    ...
):
    return "refusal"
```

## Tests Added or Updated

- `services/api/tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_classifies_brief_natural_confirmations` — Pins down standalone "Yes", "Sí", "Si", "Yes please", "Sí, por favor", "Yeah", "Yep", "Claro", "Por supuesto" classifying as `approve`.
- `services/api/tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_classifies_brief_natural_rejections` — Pins down standalone "No", "No.", "Nope", "No thanks", "No, gracias", "No por favor" classifying as `reject`.
- `services/api/tests/unit/test_intent_classification.py::TestUserIntentClassifier::test_rejects_yes_plus_new_instruction_as_approval` — Verifies "Yes, remember to check the stock tomorrow" and variants do not classify as `approve`.
- `services/api/tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_brief_natural_confirmation_persists_memory_rule` — End-to-end integration test verifying "Yes" commits proposal to memory repository and records `approved` audit log.
- `services/api/tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_brief_natural_rejection_discards_memory_rule` — End-to-end integration test verifying "No" rejects proposal and records `rejected` audit log.
- `services/api/tests/integration/test_agent_memory_lifecycle.py::TestAgentMemoryLifecycleIntegration::test_compound_instruction_discards_proposal_and_executes_query` — End-to-end integration test verifying "Yes, remember to check current stock for SKU-401" discards proposal and executes the inventory tool query in the same turn.

## Local Verification

- Commands run:
  - `services\api\.venv\Scripts\pytest.exe -o addopts="" services/api/tests/unit/test_intent_classification.py services/api/tests/integration/test_agent_memory_lifecycle.py` → 69 passed, 2 warnings in 387s.
- Manual checks:
  - Verified exact match behavior and rejection behavior via standalone Python harness.

## Deviations from Assessment

- Expanded scope slightly to include `services/api/application/services/agent_workflow.py`: `route_after_intake` previously unconditionally routed inputs shorter than `MIN_QUERY_LENGTH` (3 characters) to `refusal_node`. Because natural negative confirmations ("No") and Spanish affirmative confirmations ("Sí") are 2 characters in length, `route_after_intake` was updated to check `(len(query) < MIN_QUERY_LENGTH and proposal_resolution is None)`, matching the guard condition in `intake_node`.

## Follow-ups

- None.
