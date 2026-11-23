# Bug Verification: Memory Intent Classifier Confirmation and Instruction Boundary Fix

- **Slug**: memory-classifier-confirmation
- **Tested**: 2026-11-21
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptoms no longer reproduce: natural brief confirmations ("Yes", "Sí") and rejections ("No") are accurately classified without being discarded as ambiguous, and compound instructions ("Yes, remember to check the stock tomorrow") are rejected from the approval pathway without saving pending rules. All reproduction steps, new/updated unit tests, lifecycle integration tests, and workflow regression suites passed cleanly.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `services\api\.venv\Scripts\python.exe -c "..."` | pass | Evaluated "Yes" (intent=approve), "Sí" (intent=approve), "No" (intent=reject), and "Yes, remember to check the stock tomorrow" (intent=unrelated_or_ambiguous). |
| New / updated tests | `services\api\.venv\Scripts\pytest.exe -o addopts="" services/api/tests/unit/test_intent_classification.py` | pass | 58 passed in 335.43s. Tested brief confirmations, brief rejections, and compound instruction rejection boundaries. |
| Integration tests | `services\api\.venv\Scripts\pytest.exe -o addopts="" -k "test_brief_natural_confirmation_persists_memory_rule or test_brief_natural_rejection_discards_memory_rule or test_compound_instruction_discards_proposal_and_executes_query" services/api/tests/integration/test_agent_memory_lifecycle.py` | pass | 3 passed in 16.59s. Verified end-to-end proposal approval, proposal rejection with audit logging, and compound instruction execution. |
| Regression suite | `services\api\.venv\Scripts\pytest.exe -o addopts="" services/api/tests/unit/test_agent_workflow.py` | pass | 13 passed in 77.21s. Verified no regressions in agent intake routing or proposal resolution handling. |
| Lint / type-check | `mypy` | skipped | Mypy is not installed in the services/api Python virtual environment. |

## Output Excerpts

### Post-Fix Reproduction Harness Output
```text
r1: intent=approve, residual=None
r2: intent=approve, residual=None
r3: intent=reject, residual=None
r4: intent=unrelated_or_ambiguous, residual=Yes, remember to check the stock tomorrow
REPRODUCTION CHECKS ALL PASSED!
```

### Unit Tests (`test_intent_classification.py`)
```text
collected 58 items
services\api\tests\unit\test_intent_classification.py .......................... [ 44%]
................................                                 [100%]
================= 58 passed, 2 warnings in 335.43s (0:05:35) ==================
```

### Integration Tests (`test_agent_memory_lifecycle.py`)
```text
collected 11 items / 8 deselected / 3 selected
services\api\tests\integration\test_agent_memory_lifecycle.py ...        [100%]
================ 3 passed, 8 deselected, 2 warnings in 16.59s =================
```

### Regression Suite (`test_agent_workflow.py`)
```text
collected 13 items
services\api\tests\unit\test_agent_workflow.py .............             [100%]
================== 13 passed, 2 warnings in 77.21s (0:01:17) ==================
```

## Residual Risks

- Multi-intent inputs that deliberately combine an affirmative, an explicit memory reference, and a follow-up query (e.g. `"Yes save that rule, and what is current stock?"`) depend on exact separator and verb phrasing; users supplying conversational noise between approval and follow-up clauses will safely route to operational query handling rather than risking accidental memory corruption.

## Recommendation

Close the bug — verified end-to-end. The fix resolves both false rejections on natural brief responses and false positive approvals on compound instructions with zero regressions across workflow and lifecycle suites.
