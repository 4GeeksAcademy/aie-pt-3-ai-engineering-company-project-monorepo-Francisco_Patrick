# Bug Fix: Enforce Collocations and Deflect Polysemic Keywords in Out-of-Domain Queries

- **Slug**: guardrail-polysemic-keyword-bypass
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Refactored `InputGuardrailValidator` Layer 1 heuristics to eliminate false-positive allow classifications for out-of-domain queries containing polysemic logistics keywords (`warehouse`, `carrier`, `transit`, `package`, `inventory`). Standalone keyword matching was replaced with operational collocations in `_IN_DOMAIN_LOGISTICS_CUES`, and negative domain categories were expanded in Tier 3 (`_OUT_OF_DOMAIN_PATTERNS`) to cover gaming, sci-fi/television shows, astronomy/astrophysics, telecommunications, and quantum mechanics.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Replaced standalone polysemic keywords in `_IN_DOMAIN_LOGISTICS_CUES` with operational collocations; added `OUT_OF_DOMAIN_GAMING`, `OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING`, and extended `OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION` in Tier 3 `_OUT_OF_DOMAIN_PATTERNS`. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added `TestPolysemicKeywordGuardrailRobustness` with 15 adversarial out-of-domain test cases (including all 5 reproduction queries) and 13 legitimate customer support test cases verifying zero false negatives. |

## Diff Highlights (optional)

```python
# Tier 3 additions:
(
    "OUT_OF_DOMAIN_GAMING",
    re.compile(
        r"(?:"
        r"\b(?:videojuego|videojuegos|video\s+games?|gameplay|playstation|xbox|nintendo|death\s+stranding)\b"
        r"|\b(?:board\s+games?|juegos?\s+de\s+mesa|catan|ajedrez|chess|tabletop|role-playing\s+game|rpg)\b"
        r")",
        re.IGNORECASE,
    ),
),
(
    "OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING",
    re.compile(
        r"(?:"
        r"\b(?:exoplanet|exoplanets|exoplaneta|exoplanetas|astrof[ií]sica|astrophysics|astronomy|astronom[ií]a|venus)\b"
        r"|\b(?:quantum|cu[aá]ntic[oa]|entangled\s+particles?|part[ií]culas?\s+entrelazadas?)\b"
        r"|\b(?:radiofrecuencia|radio\s+frequency|rf\s+carrier|carrier\s+wave|onda\s+portadora|modulaci[oó]n|modulation|carrier\s+frequency|5g\b)\b"
        r"|\b(?:aircraft\s+carrier|portaaviones|carrier\s+pigeons?|palomas?\s+(?:carrier|mensajeras?)|primera\s+guerra\s+mundial|segunda\s+guerra\s+mundial|world\s+war|wwi|wwii)\b"
        r")",
        re.IGNORECASE,
    ),
),

# Tier 5 collocations:
# Couriers and carriers: collocations required for generic 'carrier' and 'transportista'
r"|\b(?:(?:our|the|this|that|assigned|delivery|shipping|preferred|which|what)\s+carriers?|carriers?\s+(?:assigned|assignment|status|delay|delays|tracking|rates?|fee|fees|service|services|delivery|deliveries|delivers|pickup|partner|partners|contract))\b"
# Transit: collocations required for transit / tránsito
r"|\b(?:(?:in|en)\s+transit|(?:in|en)\s+tr[aá]nsito|transit\s+(?:time|times|delay|delays|status|hub|facility)|tiempo\s+de\s+tr[aá]nsito|tr[aá]nsito\s+del?\s+(?:env[ií]o|paquete|pedido))\b"
# Packaging: collocations required for package / paquete
r"|\b(?:(?:my|your|our|the|this|that|trackflow)\s+packages?|packages?\s+(?:tracking|status|delayed|lost|missing|damaged|delivery|deliveries|shipped|arrival|label|insurance|pickup|weight|dimensions|size))\b"
# Warehouses & facilities: collocations required
r"|\b(?:(?:our|the|this|that|your|trackflow|local|zaragoza|los\s+angeles)\s+(?:[a-z]+\s+)?warehouses?|warehouses?\s+(?:location|address|hours|pickup|operations|stock|inventory|open|closed|staff|facility|facilities)|(?:address|location|hours)\s+of\s+(?:the\s+)?(?:[a-z]+\s+)?warehouses?|warehousing\s+(?:services?|operations?|facility|facilities))\b"
# Inventory & stock: collocations required
r"|\b(?:(?:trackflow|warehouse|product|item|sku|unit|units|current|available|catalog|physical)\s+inventory|inventory\s+(?:level|levels|count|status|management|audit|check|availability|shortage))\b"
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestPolysemicKeywordGuardrailRobustness::test_polysemic_out_of_domain_queries_are_deflected` — Verifies 15 adversarial and cross-disciplinary queries (including TV series "Warehouse 13", astrophysics exoplanet transit, WWI carrier pigeons, "Death Stranding" package weight, and "Catan" inventory) deflect with `action="deflect"` and `input_category="out_of_domain"`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestPolysemicKeywordGuardrailRobustness::test_legitimate_logistics_collocations_remain_allowed` — Verifies 13 legitimate customer support queries in English and Spanish with operational context (e.g. "What is the address of the Los Angeles warehouse?", "Which carrier is handling my delivery?", "¿Dónde está mi paquete?") pass with `action="allow"` and `input_category="in_domain"`.

## Local Verification

- Commands run: `uv run --project services/api pytest services/api/tests/unit/test_agent_guardrails_input.py` → 87 passed in 0.68s (100% pass rate).
- Manual checks: Verified reproduction cases 1 through 5 in `assessment.md` produce `action="deflect"`, `input_category="out_of_domain"`, and return the standard TrackFlow neutral deflection message.

## Deviations from Assessment

None. The implementation followed the preferred remediation exactly: restricting polysemic keywords to operational collocations in `_IN_DOMAIN_LOGISTICS_CUES` and adding negative domain regex patterns in Tier 3 `_OUT_OF_DOMAIN_PATTERNS`.

## Follow-ups

- Monitor Layer 1 telemetry for edge cases where colloquial phrasing might not match common collocations, expanding the collocation whitelist as needed.
- Consider evaluating Alternative 1 (lightweight embedding centroid gate) in a future iteration as an added safety layer behind regex evaluation.
