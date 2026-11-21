# Bug Assessment: Guardrails PR Review & Hardening Fixes (030)

- **Slug**: 030-agent-guardrails-fixes
- **Created**: 2026-11-21
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> # Revisiones
>
> 1. **Alcance de la PR (mezcla de `029-agent-memory-self-improvement` / `029-agent-memory-fixes` y `030-agent-guardrails`):**
> El diff incluye archivos completos de la Parte 1 (`029-agent-memory-self-improvement` + `.specify/bugs/029-agent-memory-fixes/` + `presentation/api/v1/memory.py` + `main.py`) junto con los de la Parte 2 (`030-agent-guardrails`). Si el flujo del curso espera que la rama `feature/agent-guardrails` parta de Part 1 ya fusionada en `main`, revisa si conviene separar o confirmar que `main` no tiene esos commits previos.
>
> 2. **Inconsistencia menor en la firma de `ContextSanitizerPort` (`guardrail-ports.md` vs. `ports.py` / `agent_guardrails.py`):**
> En `specs/030-agent-guardrails/contracts/guardrail-ports.md` el método abstracto aparece como `sanitize_text_Chunk` (con `C` mayúscula), mientras que en `ports.py` y `agent_guardrails.py` el método principal es `sanitize_text_chunk` (con alias `sanitize_Text_Chunk`). Conviene unificar el nombre en el contrato para evitar confusión en mocks/implementaciones de terceros.
>
> 3. **Resolución de país cuando `session_context` es `None` en `AuthorizationGuardrailValidator`:**
> Si `session_context is None` y no hay ubicación explícita en la consulta, `resolved_country` cae por defecto en `"US"`. Para consultas sin contexto ni país explícito, verifica que no se asuma `"US"` de forma engañosa cuando se consulten políticas generales.
>
> 4. **Reset de métricas en sesiones de prueba:**
> `GuardrailObservabilityService` tiene `clear()`, pero ni el endpoint `GET /api/v1/agent/guardrails/summary` ni el CLI exponen un flag `--reset` (útil si un operador quiere limpiar contadores entre tandas manuales sin reiniciar el proceso).

## Symptom

1. **Inflated PR diff mixing Feature 029 and Feature 030**: Comparing `feature/agent-guardrails` with `origin/main` reveals 57 modified/added files (+12,493 lines) instead of only the 30 files (+5,895 lines) belonging to Feature 030 (`030-agent-guardrails`). This occurred because `feature/agent-guardrails` branched from `feature/agent-memory` before `feature/agent-memory` was merged into `main`.
2. **Contract method typo in `ContextSanitizerPort`**: In `specs/030-agent-guardrails/contracts/guardrail-ports.md:68`, the abstract method signature is declared as `sanitize_text_Chunk` (camelCase `Chunk`), while Python code in `ports.py:334` and `agent_guardrails.py:669` standardizes on `sanitize_text_chunk`, forcing a backward-compatibility alias `sanitize_Text_Chunk` in the implementation.
3. **Misleading "US" country default in unauthenticated / generic policy queries**: In `AuthorizationGuardrailValidator.evaluate_authorization_and_policy()` (`agent_guardrails.py:491`), `resolved_country` defaults unconditionally to `"US"` whenever `session_context is None` and no explicit order location was parsed. As a result, generic questions about policies (e.g., asking about Spanish returns or general policies in Spanish) are falsely attributed to `"US"`, causing improper cross-country blocks (`CROSS_COUNTRY_POLICY_MIXING`) or injecting `"Active Authoritative Jurisdiction: US"` into the prompt.
4. **No metric reset capability in CLI or API**: While `GuardrailObservabilityService` provides an in-memory `clear()` method, neither the CLI (`guardrail_observability.py`) nor the HTTP endpoint (`GET /api/v1/agent/guardrails/summary`) exposes a `--reset` option or reset endpoint. Operators and automated test runners cannot reset trigger counters between test suites without terminating the process.

## Reproduction

1. **PR diff scope check**:
   ```bash
   git log origin/main..HEAD --oneline
   # Shows 029 commits (6750cc8, 89b88f7, e918a7f) alongside 030 commits (f0f89ae, 02735fe).
   git diff --stat origin/main...HEAD
   # Shows 57 files changed (+12,493 lines), including memory.py, tinydb memory repositories, and 029 specs.
   ```
2. **Contract casing mismatch**:
   Inspect line 68 of `specs/030-agent-guardrails/contracts/guardrail-ports.md`:
   ```python
   def sanitize_text_Chunk(self, text: str, source_label: str = "context") -> GuardrailEvaluationResult:
   ```
   Compare with `services/api/domain/agent/ports.py:334`:
   ```python
   def sanitize_text_chunk(self, text: str, source_label: str = "context") -> GuardrailEvaluationResult:
   ```
3. **Unauthenticated query country resolution**:
   Execute:
   ```python
   val = AuthorizationGuardrailValidator()
   res = val.evaluate_authorization_and_policy("¿Cuál es la política general de devoluciones?", session_context=None)
   print(res.resolved_country)  # Outputs 'US' despite no order or US location mentioned!
   ```
   If a user asks `"Aplica la política de devoluciones de España para compras online"` with `session_context=None`, the validator blocks with `CROSS_COUNTRY_POLICY_MIXING` citing a non-existent Los Angeles order!
4. **Observability CLI & API reset gap**:
   Run `uv run python -m application.services.guardrail_observability --help`. Notice there is no `--reset` flag. Send `GET /api/v1/agent/guardrails/summary`; notice there is no query parameter `reset=true` or separate reset route.

## Suspected Code Paths

- `specs/030-agent-guardrails/contracts/guardrail-ports.md:68` — Method name typo `sanitize_text_Chunk`.
- `services/api/domain/agent/ports.py:334-340` — Port contract method `sanitize_text_chunk`.
- `services/api/application/services/agent_guardrails.py:484-492, 568-605, 751-757` — Unconditional fallback to `"US"` when `session_context is None`; shim method `sanitize_Text_Chunk`.
- `services/api/application/services/agent_workflow.py:128-138` — System prompt jurisdiction injection when `resolved_country` is present.
- `services/api/application/services/guardrail_observability.py:382-416` — CLI parser missing `--reset`.
- `services/api/presentation/api/v1/agent.py:191-236` — Summary endpoint lacking reset query param or endpoint.
- Git branch history — `feature/agent-guardrails` branched from `feature/agent-memory`.

## Root Cause Hypothesis

- **PR Scope**: Standard linear git workflow without merging or rebasing onto `main` after Part 1 was finished.
- **Contract Typo**: Manual specification editing in `guardrail-ports.md` introduced an unintended uppercase `C` in `sanitize_text_Chunk`.
- **False-positive US Default**: Defensive programming assumed every session must resolve to a valid `OperatingCountry` ("US" or "ES"), ignoring unauthenticated or generic queries where no order or location exists (`resolved_country` should be `None`).
- **Observability Ergonomics**: `clear()` was implemented on the service layer for testing but was not wired into the presentation layer (CLI and FastAPI router).

Confidence: High.

## Proposed Remediation

### Preferred Fix

1. **PR Scope & Integration Workflow**:
   - Merge `feature/agent-memory` (Part 1) into `main` first (or set PR 030 base branch to `feature/agent-memory` on GitHub).
   - Once Part 1 is in `main`, rebase `feature/agent-guardrails` onto `origin/main` (`git checkout feature/agent-guardrails && git rebase origin/main`). The PR against `main` will then cleanly reflect only the 30 files of Feature 030.
2. **Contract Alignment (`guardrail-ports.md`)**:
   - In `specs/030-agent-guardrails/contracts/guardrail-ports.md`, change `def sanitize_text_Chunk` to `def sanitize_text_chunk`.
   - Maintain the alias `sanitize_Text_Chunk` in `agent_guardrails.py` to prevent breaking any callers using the old casing.
3. **Country Resolution Neutrality (`AuthorizationGuardrailValidator`)**:
   - In `AuthorizationGuardrailValidator.evaluate_authorization_and_policy`:
     - If `session_context is None`:
       - `resolved_country = explicit_country` (which is `None` if no specific city/country is referenced).
     - When evaluating `CROSS_COUNTRY_POLICY_MIXING`:
       - Only trigger cross-country mixing blocks if `resolved_country is not None` (i.e. tied to a concrete order or verified session) AND `requested_policy_country != resolved_country`.
     - In `agent_workflow.py`, only append the authoritative jurisdiction prompt note if `resolved_country is not None`.
4. **Expose Metrics Reset in CLI and HTTP API**:
   - In `services/api/application/services/guardrail_observability.py`:
     - Add `--reset` flag to `main()`. When present, call `obs.clear()` and report `"Guardrail observability metrics and audit events cleared."`.
   - In `services/api/presentation/api/v1/agent.py`:
     - Add `reset: bool = Query(default=False, description="When true, clear in-memory guardrail counters and events after returning summary")` to `get_guardrail_summary()`, calling `observability.clear()` after snapshot generation, or add `POST /guardrails/reset`.
     - Update `specs/030-agent-guardrails/contracts/agent-guardrails-api.yaml` to document the parameter.

**Files likely to change**:
- `specs/030-agent-guardrails/contracts/guardrail-ports.md`
- `specs/030-agent-guardrails/contracts/agent-guardrails-api.yaml`
- `services/api/application/services/agent_guardrails.py`
- `services/api/application/services/agent_workflow.py`
- `services/api/application/services/guardrail_observability.py`
- `services/api/presentation/api/v1/agent.py`
- `services/api/tests/unit/test_agent_guardrails_authorization.py`
- `services/api/tests/integration/test_agent_guardrails_observability.py`

**Tests to add or update**:
- Test in `test_agent_guardrails_authorization.py`: Generic policy query with `session_context=None` returns `resolved_country=None` and `action="allow"` without blocking.
- Test in `test_agent_guardrails_observability.py`: Calling summary endpoint with `reset=True` clears counters for subsequent requests.
- Test in CLI unit tests: `--reset` flag resets stored metrics.

## Risks & Considerations

- **Git Rebase Risk**: Rebasing onto `main` before `feature/agent-memory` is merged into `main` would duplicate or complicate history. Part 1 must be merged into `main` first, or PR base temporarily targeted at `feature/agent-memory`.
- **Backward Compatibility**: Keep `sanitize_Text_Chunk` method alias in `agent_guardrails.py` so any existing tests or code continue to run cleanly.
- **Fail-Closed Security**: Ensure that order lookups (where an order ID is present) continue to fail-closed (`MISSING_SESSION_AUTHORIZATION`) when `session_context is None`. Only general unauthenticated non-order policy questions should leave `resolved_country=None`.

## Open Questions

- Confirm with the repository owner whether `feature/agent-memory` will be merged directly to `main` via GitHub PR first, or if Part 1 and Part 2 are intended to be reviewed in stacked PRs.
