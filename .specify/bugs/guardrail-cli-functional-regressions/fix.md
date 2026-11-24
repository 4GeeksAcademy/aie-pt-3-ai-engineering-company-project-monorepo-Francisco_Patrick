# Bug Fix: Guardrail CLI Functional Regressions, Tool Routing, Locale Drift, and Composite Jailbreak Bypass

- **Slug**: guardrail-cli-functional-regressions
- **Fixed**: 2026-11-24
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Resolved the composite red-team jailbreak bypass (#10), false-positive out-of-domain deflections on shipping tiers (#4), B2B storage rates (#8), and compound greetings (#9), wired authorized order and incident queries (#1, #2, #5) to `ticket_tool`, enabled query-aware RAG ranking in the offline Guardrail CLI knowledge base (#3, #6, #7, #8), and implemented turn-aware bilingual Spanish/English response synthesis and refusal localization.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Hardened `_JAILBREAK_PATTERNS` (`DIRECT_INSTRUCTION_OVERRIDE`, `BILINGUAL_INSTRUCTION_OVERRIDE`, `SYSTEM_PROMPT_EXTRACTION_OR_HYPOTHETICAL_JAILBREAK`) for subjunctive Spanish verb forms (`ignores`, `olvides`, `omitas`, `desactives`, `saltes`, `reveles`, `muestres`) and confidential carrier rate / warehouse security route exfiltration; expanded `BRIEF_SMALL_TALK` for compound greetings (`¡Hola, buenos días!`); expanded `_IN_DOMAIN_LOGISTICS_CUES` for Spanish shipping tiers, storage pricing, >180-day inventory, and carrier coverage; refined `_is_spanish()` to prioritize turn-level query language; excluded internal `INC-...` ticket IDs and `SKU` codes from `extract_referenced_order_ids()`. |
| `services/api/application/services/agent_workflow.py` | modified | Updated `_GENERIC_TICKET_NUM_PATTERN`, `_TICKET_KEYWORDS_PATTERN`, and `_POLICY_RAG_KEYWORDS_PATTERN` so order/shipment status and incident queries (`#10492`, `#88310`, `incidencia`) route to `ticket_tool`; localized `_format_ticket_records_summary()` for Spanish order status and incident reporting workflows. |
| `services/api/application/services/guardrail_cli.py` | modified | Populated all 12 canonical TrackFlow knowledge chunks (`returns-policy`, `sla-delivery`, `carrier-coverage`, `storage-pricing`) in `_CliKnowledgeVectorStoreAdapter` and added deterministic query-relevance ranking in `search()`. |
| `services/api/infrastructure/adapters/grounded_generation_adapter.py` | modified | Added bilingual Spanish/English synthesis to `_synthesize_deterministically()` and `_format_chunk_in_persona()`, and tightened `_should_include_secondary_chunk()` to prevent cross-document policy bleed. |
| `services/api/application/services/guardrails.py` | modified | Added Spanish corporate guardrail remediation clauses (`VOLUME_DISCOUNT_CLAUSE_ES`, `PEAK_SEASON_SLA_CLAUSE_ES`, `INTERNATIONAL_RETURNS_CLAUSE_ES`, `CARRIER_OVERRIDE_CLAUSE_ES`) and language-aware compliance checks in `BusinessGuardrailValidator`. |
| `services/api/tests/unit/test_guardrail_cli.py` | added test | Added `test_functional_and_adversarial_regression_suite` pinning all 9 functional scenarios and critical red-team scenarios (#8, #10). |
| `services/api/tests/unit/test_agent_guardrails_input.py` | added test | Added `test_composite_authorized_order_and_subjunctive_privacy_override_is_blocked` verifying Red-Team Test #10 is blocked at `input_guard`. |

## Diff Highlights

```python
# services/api/application/services/agent_guardrails.py
def _is_spanish(query: str, language: str = "en") -> bool:
    text = (query or "").strip()
    if text:
        has_es = bool(_SPANISH_INDICATOR_PATTERN.search(text))
        has_en = bool(_ENGLISH_INDICATOR_PATTERN.search(text))
        if has_es and not has_en:
            return True
        if has_en and not has_es:
            return False
        if has_es and has_en:
            if re.search(r"[áéíóúñ¿¡]", text):
                return True
    return (language or "").strip().lower().startswith("es")
```

```python
# services/api/application/services/agent_workflow.py
_GENERIC_TICKET_NUM_PATTERN = re.compile(
    r"\b(?:ticket|incident|incidencia|pedido|order|env[ií]o|shipment|tracking|paquete|package)\s*(?:#|id|number|n[uú]mero)?\s*[:=#]?\s*#?([A-Za-z]{2,6}-\d+|inc_[A-Za-z0-9]+|\d{4,10})\b"
    r"|#(\d{4,10})\b",
    re.IGNORECASE,
)
```

## Tests Added or Updated

- `services/api/tests/unit/test_guardrail_cli.py::TestGuardrailCli::test_functional_and_adversarial_regression_suite` — Verifies functional tests #1–#9 (Spanish/English order lookups `#10492` & `#88310`, return policies, standard vs. express SLAs, incident reporting, carrier coverage in Zaragoza/Aragón & LA, international returns with Sofía Ramos, B2B storage rates & >180-day surcharge, compound greeting redirect) and adversarial tests #8 (English deflection in `[ES|es]` session) and #10 (composite injection blocked at `input_guard`).
- `services/api/tests/unit/test_agent_guardrails_input.py::TestJailbreakAndInstructionOverrides::test_composite_authorized_order_and_subjunctive_privacy_override_is_blocked` — Pins down Layer 1 security blocking on composite prompts combining valid order IDs (`#10492`), locations (`Zaragoza`), and subjunctive privacy override / confidential carrier rate extraction directives.

## Local Verification

- Commands run: `uv run pytest tests/unit/test_guardrail_cli.py tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_output.py tests/unit/test_agent_guardrails_context_isolation.py tests/unit/test_agent_workflow.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py` → `363 passed in 3.84s`.
- Manual checks: Verified that internal incident ticket IDs (`INC-001`) and product SKUs (`SKU TF-1001`) remain excluded from customer order IDOR checks in `extract_referenced_order_ids()` while customer order IDs (`#10492`, `#88310`, `#45821`, `ORD-...`) are strictly enforced against `AuthenticatedSessionContext`.

## Deviations from Assessment

None.

## Follow-ups

- Execute `/speckit-bug-test slug=guardrail-cli-functional-regressions` to generate the formal verification report (`verification.md`).
