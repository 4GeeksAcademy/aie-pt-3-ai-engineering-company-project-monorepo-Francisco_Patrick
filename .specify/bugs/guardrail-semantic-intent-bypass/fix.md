# Bug Fix: Neutralize Guardrail Semantic Intent Bypass via Alien Domain Patterns and Fast Semantic Router

- **Slug**: guardrail-semantic-intent-bypass
- **Fixed**: 2026-11-23T16:18:30+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Neutralized semantic intent bypasses in `InputGuardrailValidator` where queries belonging to out-of-domain disciplines (classical archaeology, planetary exploration, biohazard virology, military warfare, and art heritage) bypassed frontline guardrails by embedding valid logistics collocations. Added targeted negative exclusion patterns across alien domains in Stage 1 and implemented an embedded `FastIntentSemanticRouter` wired into production dependency injection.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added negative out-of-domain regexes (`OUT_OF_DOMAIN_SPACE_EXPLORATION`, `OUT_OF_DOMAIN_MILITARY_AND_WARFARE`, `OUT_OF_DOMAIN_ANTIQUITIES_AND_ARCHAEOLOGY`, `OUT_OF_DOMAIN_BIOHAZARD_AND_PATHOGENS`) to `_OUT_OF_DOMAIN_PATTERNS` and implemented `FastIntentSemanticRouter` |
| `services/api/presentation/dependencies.py` | modified | Injected `FastIntentSemanticRouter()` into `InputGuardrailValidator` via `get_input_guardrail_dep` |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added tests for 5 reproduction queries, `FastIntentSemanticRouter` classification, and dependency injection wiring |

## Diff Highlights (optional)

```python
# Stage 1: Added negative exclusion patterns for alien domains
(
    "OUT_OF_DOMAIN_SPACE_EXPLORATION",
    re.compile(
        r"(?:\b(?:nasa|mars|marte|lunar|moon\s+rocks?|rocas?\s+lunares?|hubble|james\s+webb|orbital\s+trajectory|orbit\s+insertion|spacecraft|cohete|cohetes|espacial|sat[eé]lites?|deep\s+space|planetary\s+exploration)\b|\b(?:space\s+mission|misi[oó]n\s+espacial|space\s+probe|alien\s+planet|astronavigation)\b)",
        re.IGNORECASE,
    ),
),
(
    "OUT_OF_DOMAIN_MILITARY_AND_WARFARE",
    re.compile(
        r"(?:\b(?:nato|otan|ammunition|arsenal|arsenales|warfare|geneva\s+convention|convenci[oó]n\s+de\s+ginebra|prisioneros\s+de\s+guerra|prisoners?\s+of\s+war)\b|\b(?:torpedeamiento|misil|misiles|missiles?|armamento|weaponry|weapons?|military\s+ordnance|bal[ií]stica|ballistics?|naval\s+warfare|guerra\s+naval)\b|\b(?:military\s+logistics|log[ií]stica\s+militar|munition|municiones)\b)",
        re.IGNORECASE,
    ),
),
(
    "OUT_OF_DOMAIN_ANTIQUITIES_AND_ARCHAEOLOGY",
    re.compile(
        r"(?:\b(?:etruscan|etrusc[oa]s?|sarc[oó]fago|sarc[oó]fagos|sarcophagus|pharaonic|fara[oó]nic[oa]s?|archaeolog|arqueolog)\b|\b(?:renaissance\s+masterwork|renaissance\s+masterworks|renaissance\s+art|obras?\s+renacentistas?|escultura\s+romana|cer[aá]micas?\s+etruscas?|cer[aá]micas?\s+antiguas?|ancient\s+pottery|artefactos?\s+arqueol[oó]gicos?|archaeological\s+artifacts?|art\s+heritage|patrimonio\s+art[ií]stico)\b)",
        re.IGNORECASE,
    ),
),
(
    "OUT_OF_DOMAIN_BIOHAZARD_AND_PATHOGENS",
    re.compile(
        r"(?:\b(?:bsl-4|bsl-3|biosafety\s+level|nivel\s+de\s+bioseguridad|pathogen|pathogens|pat[oó]geno|pat[oó]genos|live\s+virus|virus\s+vivo|virus\s+pat[oó]geno)\b|\b(?:antiof[ií]dico|biol[oó]gico\s+peligroso|biohazard|biological\s+weapons?|armas?\s+biol[oó]gicas?|anthrax|[aá]ntrax|ebola|[eé]bola)\b)",
        re.IGNORECASE,
    ),
),

# Stage 2: FastIntentSemanticRouter
class FastIntentSemanticRouter:
    def classify(self, query: str) -> str:
        cleaned = (query or "").strip()
        if not cleaned:
            return "IN_DOMAIN"
        for reason_code, pattern in _OUT_OF_DOMAIN_PATTERNS:
            if pattern.search(cleaned):
                if reason_code == "OUT_OF_DOMAIN_WEATHER":
                    if _COLD_CHAIN_LOGISTICS_PATTERN.search(cleaned):
                        continue
                    if re.search(r"\btiempo\s+de\s+(?:tr[aá]nsito|entrega|env[ií]o|espera|despacho|procesamiento)\b", cleaned, re.IGNORECASE):
                        continue
                return "OUT_OF_DOMAIN"
        if self._in_domain_cues.search(cleaned) or any(p.search(cleaned) for p in self._order_patterns):
            return "IN_DOMAIN"
        return "OUT_OF_DOMAIN"
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestBoundaryConditionHardeningAndLexicalDeflection::test_reproduction_cases_guardrail_semantic_intent_bypass_deflected` — verifies that 5 cross-disciplinary queries (ancient pottery, NASA Mars cargo, BSL-4 virology, NATO ammunition return policy, and stolen renaissance masterworks) are deflected with `action="deflect"` and `input_category="out_of_domain"`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_fast_intent_semantic_router_direct_classification` — verifies direct classification of `FastIntentSemanticRouter` across alien domains and genuine logistics requests (cold-chain, tracking, incidents).
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_input_guardrail_dep_wires_semantic_router` — verifies dependency provider instantiation with `FastIntentSemanticRouter` wired into `InputGuardrailValidator`.

## Local Verification

- Commands run:
  - `uv run pytest tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_output.py tests/unit/test_agent_guardrails_context_isolation.py` → 274 passed in 1.85s (zero failures).
  - `uv run pytest tests/unit/test_dependencies.py` → 2 passed in 0.06s.
  - Manual verification script with the 5 reproduction cases → All 5 cases deflect as expected with descriptive `OUT_OF_DOMAIN_*` reason codes.

## Deviations from Assessment

None. All preferred remediation steps from `assessment.md` (Stage 1 negative exclusion patterns and Stage 2 semantic router activation in dependency injection) were implemented and verified.

## Follow-ups

- Continue monitoring frontline input guardrail deflection logs via `GuardrailObservabilityService` to identify emerging cross-domain collocations.
