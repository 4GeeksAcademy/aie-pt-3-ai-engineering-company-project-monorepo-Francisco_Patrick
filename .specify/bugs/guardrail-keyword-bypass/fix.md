# Bug Fix: Guardrail Keyword-Matching Bypass via In-Domain Terminology

- **Slug**: guardrail-keyword-bypass
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added negative out-of-domain pattern categories (dining & hospitality, entertainment & fiction, biography & personal trivia) to Layer 1 input guardrails and disambiguated polysemous `"order"` keywords so out-of-domain inquiries embedding logistics terms are deflected rather than allowed into downstream agent workflows.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added `OUT_OF_DOMAIN_DINING_OR_HOSPITALITY`, `OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION`, and `OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL` patterns to `_OUT_OF_DOMAIN_PATTERNS` (Tier 3); replaced bare `order|orders` in `_IN_DOMAIN_LOGISTICS_CUES` (Tier 5) with contextual logistics collocations and negative lookahead for non-logistics usages. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added 5 parameterized negative test cases for deflected queries (bilingual) and 4 parameterized positive test cases for legitimate logistics inquiries containing carrier/order/warehouse keywords. |

## Diff Highlights (optional)

```python
# Added to _OUT_OF_DOMAIN_PATTERNS (Tier 3)
(
    "OUT_OF_DOMAIN_DINING_OR_HOSPITALITY",
    re.compile(
        r"(?:"
        r"\b(?:restaurant|restaurants|cafe|cafes|cafeteria|cafeterias|bar|bars|diner|diners|bistro|pizzeria)\b"
        r"|\b(?:restaurante|restaurantes|cafeter[ií]a|cafeter[ií]as|bar|bares|pizzer[ií]a)\b"
        r"|\b(?:dinner|lunch|breakfast|brunch|cenar|almorzar|desayunar|cena|almuerzo|desayuno)\b"
        r"|\b(?:dining|where\s+to\s+eat|places?\s+to\s+eat|d[oó]nde\s+comer|sitio\s+para\s+comer)\b"
        r"|\b(?:hotel|hotels|motel|motels|hostel|hostels|hoteles)\b"
        r"|\b(?:fast\s+food|food\s+near|comida\s+(?:cerca|r[aá]pida))\b"
        r")",
        re.IGNORECASE,
    ),
),
(
    "OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION",
    re.compile(
        r"(?:"
        r"\b(?:order\s+of\s+the\s+phoenix|harry\s+potter|lord\s+of\s+the\s+rings|star\s+wars)\b"
        r"|\b(?:movie|movies|film|films|cinema|pel[ií]cula|pel[ií]culas|cine)\b"
        r"|\b(?:actor|actors|actress|actresses|actores|actriz|actrices)\b"
        r"|\b(?:novel|novels|novela|novelas|fiction|ficci[oó]n)\b"
        r"|\b(?:song|songs|canci[oó]n|canciones|singer|singers|cantante|cantantes|music\s+band|album|albums)\b"
        r")",
        re.IGNORECASE,
    ),
),
(
    "OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL",
    re.compile(
        r"(?:"
        r"\b(?:how\s+tall\s+is|cu[aá]nto\s+mide)\b"
        r"|\b(?:how\s+old\s+is|cu[aá]ntos\s+a[ñn]os\s+tiene)\b"
        r"|\b(?:(?:height|age)\s+of\s+(?:the\s+)?(?:[a-z0-9_-]+\s+)?(?:ceo|president|founder|director|person|[A-Z][a-z]+))\b"
        r"|\b(?:(?:altura|edad)\s+de\s+(?:el\s+|la\s+|del\s+)?(?:[a-z0-9_-]+\s+)?(?:ceo|presidente|fundador|director|persona|[A-Z][a-z]+))\b"
        r"|\b(?:net\s+worth\s+of|salary\s+of|patrimonio\s+de|salario\s+de|sueldo\s+de)\b"
        r"|\b(?:who\s+is\s+the\s+ceo\s+of|qui[eé]n\s+es\s+el\s+ceo\s+de|ceo\s+(?:of|de))\b"
        r"|\b(?:biography\s+of|biograf[ií]a\s+de|who\s+is\s+(?:the\s+)?founder\s+of|fundador\s+de)\b"
        r")",
        re.IGNORECASE,
    ),
),
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_out_of_domain_queries_are_deflected_with_neutral_message`
  - `fedex_ceo_height_en`: `"how tall is the FedEx CEO?"` -> deflected (`action="deflect"`, `input_category="out_of_domain"`)
  - `order_of_the_phoenix_meaning_en`: `"what is the meaning of the Order of the Phoenix?"` -> deflected (`action="deflect"`, `input_category="out_of_domain"`)
  - `closest_restaurant_to_warehouse_en`: `"which restaurant is closest to the warehouse?"` -> deflected (`action="deflect"`, `input_category="out_of_domain"`)
  - `fedex_ceo_height_es`: `"¿cuánto mide el CEO de FedEx?"` -> deflected (`action="deflect"`, `input_category="out_of_domain"`)
  - `closest_restaurant_to_warehouse_es`: `"¿qué restaurante queda más cerca del almacén?"` -> deflected (`action="deflect"`, `input_category="out_of_domain"`)
- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_in_domain_queries_are_allowed`
  - `"When was my FedEx order shipped?"` -> allowed (`action="allow"`, `input_category="in_domain"`)
  - `"What is the address of the Los Angeles warehouse?"` -> allowed (`action="allow"`, `input_category="in_domain"`)
  - `"I want to check the status of my order #45821."` -> allowed (`action="allow"`, `input_category="in_domain"`)
  - `"How does FedEx handle lost packages?"` -> allowed (`action="allow"`, `input_category="in_domain"`)

## Local Verification

- Commands run:
  - `& "services/api/.venv/Scripts/python.exe" -m pytest services/api/tests/unit/test_agent_guardrails_input.py` → 59 passed, 0 failed in 0.54s
  - Direct execution of reproduction queries and edge cases via Python script:
    - `"how tall is the FedEx CEO?"` → `action="deflect"`, `input_category="out_of_domain"`, `reason_code="OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL"`
    - `"what is the meaning of the Order of the Phoenix?"` → `action="deflect"`, `input_category="out_of_domain"`, `reason_code="OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION"`
    - `"which restaurant is closest to the warehouse?"` → `action="deflect"`, `input_category="out_of_domain"`, `reason_code="OUT_OF_DOMAIN_DINING_OR_HOSPITALITY"`
    - `"¿cuánto mide el CEO de FedEx?"` → `action="deflect"`, `input_category="out_of_domain"`, `reason_code="OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL"`
    - `"¿qué restaurante queda más cerca del almacén?"` → `action="deflect"`, `input_category="out_of_domain"`, `reason_code="OUT_OF_DOMAIN_DINING_OR_HOSPITALITY"`
    - `"When was my FedEx order shipped?"` → `action="allow"`, `input_category="in_domain"`, `reason_code="IN_DOMAIN_ALLOWED"`
    - `"What is the address of the Los Angeles warehouse?"` → `action="allow"`, `input_category="in_domain"`, `reason_code="IN_DOMAIN_ALLOWED"`
    - `"I want to check the status of my order #45821."` → `action="allow"`, `input_category="in_domain"`, `reason_code="IN_DOMAIN_ALLOWED"`
    - `"How does FedEx handle lost packages?"` → `action="allow"`, `input_category="in_domain"`, `reason_code="IN_DOMAIN_ALLOWED"`
- Manual checks:
  - Verified non-logistics order phrases (`"in order to succeed"`, `"explain alphabetical order"`, `"what is the Order of the Phoenix"`) do not match `_IN_DOMAIN_LOGISTICS_CUES` and deflect cleanly.

## Deviations from Assessment

None.

## Follow-ups

- Consider adding telemetry metrics tracking specific deflection reason codes (`OUT_OF_DOMAIN_DINING_OR_HOSPITALITY`, `OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION`, `OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL`) to evaluate deflection accuracy and traffic trends in production.
