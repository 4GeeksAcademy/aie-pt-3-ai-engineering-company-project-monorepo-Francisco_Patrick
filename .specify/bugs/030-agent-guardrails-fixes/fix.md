# Bug Fix: Guardrails PR Review & Hardening Fixes (030)

- **Slug**: 030-agent-guardrails-fixes
- **Fixed**: 2026-11-21
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Resolved contract casing in `ContextSanitizerPort`, eliminated false-positive US fallback for unauthenticated generic policy inquiries in `AuthorizationGuardrailValidator`, exposed metric reset capabilities in both the observability CLI and FastAPI endpoints, and documented the PR base branch scope alignment.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `specs/030-agent-guardrails/contracts/guardrail-ports.md` | modified | Aligned abstract method name to `def sanitize_text_chunk` (standard snake_case) |
| `specs/030-agent-guardrails/contracts/agent-guardrails-api.yaml` | modified | Documented `reset` query param on `GET /guardrails/summary`, added `POST /guardrails/reset` and schema |
| `services/api/application/services/agent_guardrails.py` | modified | Neutralized unauthenticated country resolution to `explicit_country` (`None` if no order/location) and restricted `CROSS_COUNTRY_POLICY_MIXING` to explicit non-null country contexts |
| `services/api/application/services/guardrail_observability.py` | modified | Added `--reset` command-line flag calling `obs.clear()` |
| `services/api/presentation/schemas/agent.py` | modified | Added `GuardrailResetResponseSchema` |
| `services/api/presentation/api/v1/agent.py` | modified | Added `reset: bool` query param to `get_guardrail_summary()` and registered `POST /guardrails/reset` endpoint |
| `services/api/tests/unit/test_agent_guardrails_authorization.py` | modified | Added unit tests verifying generic policy queries and Spain return queries without session context return `action='allow'` without false-positive US blocking |
| `services/api/tests/integration/test_agent_guardrails_observability.py` | modified | Added integration tests verifying `reset=True` query param, `POST /guardrails/reset`, and CLI `--reset` flag |

## Diff Highlights (optional)

```python
# services/api/application/services/agent_guardrails.py
         if session_context is not None:
             resolved_country = session_context.resolve_order_country(
                 order_id=primary_order,
                 explicit_location_country=explicit_country,
             )
         else:
-            resolved_country = explicit_country or "US"
+            resolved_country = explicit_country
```

```python
# services/api/application/services/agent_guardrails.py
         if wants_es_on_us or (
+            resolved_country is not None
+            and requested_policy_country == "ES"
+            and resolved_country == "US"
-            requested_policy_country == "ES" and resolved_country == "US"
         ):
```

```python
# services/api/presentation/api/v1/agent.py
@router.post(
    "/guardrails/reset",
    response_model=GuardrailResetResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Reset in-memory guardrail trigger counters and audit event history",
)
async def reset_guardrails(
    observability: GuardrailObservabilityPort = Depends(get_guardrail_observability_dep),
) -> GuardrailResetResponseSchema:
    await run_in_threadpool(observability.clear)
    return GuardrailResetResponseSchema(
        status="cleared",
        message="Guardrail observability metrics and audit events cleared.",
    )
```

## Tests Added or Updated

- `test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_generic_policy_query_without_session_context_has_no_country_and_is_allowed` — pins down that generic inquiries without session context or location cues resolve to `resolved_country=None` and pass with `action='allow'`.
- `test_agent_guardrails_authorization.py::TestCountryResolutionAndPolicySeparation::test_spain_policy_query_without_session_context_is_not_blocked_as_us_order` — pins down that querying Spain's return policy without active session context does not misattribute the order to Los Angeles / US or block on cross-country mixing.
- `test_agent_guardrails_observability.py::TestSupportAgentGuardrailsIntegration::test_rest_api_query_and_guardrails_summary_endpoints` — pins down `GET /guardrails/summary?reset=true` and `POST /guardrails/reset` in-memory counter clearing.
- `test_agent_guardrails_observability.py::TestSupportAgentGuardrailsIntegration::test_cli_reset_flag_clears_metrics` — pins down CLI `--reset` argument handling.

## Local Verification

- Commands run:
  - `uv run pytest tests/unit/test_agent_guardrails_authorization.py tests/integration/test_agent_guardrails_observability.py` → 16 passed in 0.33s
  - `uv run pytest -k "agent or guardrail"` → 102 passed, 368 deselected in 5.09s
- Manual checks:
  - Verified git commit tree: `feature/agent-guardrails` contains 2 commits (`f0f89ae`, `02735fe`) directly on top of `feature/agent-memory`.
  - Confirmed `ContextSanitizerPort` in `guardrail-ports.md` matches `ports.py` while preserving backward compatibility alias `sanitize_Text_Chunk` in `TwoTierContextSanitizer`.

## Deviations from Assessment

None. All four recommendations from the assessment contract were addressed directly in code, specifications, and tests.

## Follow-ups

- **PR Base Target Workflow**: In GitHub PR settings for Feature 030 (`feature/agent-guardrails`), set the base branch to `feature/agent-memory` to review only the 30 files related to guardrails, or wait until `feature/agent-memory` is merged into `origin/main` before rebasing `feature/agent-guardrails` on `origin/main`.
