# Bug Fix: Guardrail False Negatives on Open Ticket Queries and False Positive Bypass on Carrier History

- **Slug**: guardrail-ticket-domain-scoping
- **Fixed**: 2026-11-24
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Expanded Layer 1 input guardrail operational ticket patterns (`_IN_DOMAIN_LOGISTICS_CUES` and `_OPERATIONAL_LOGISTICS_ACTIONS`) to allow customer support ticket status inquiries (e.g., `"can you check open tickets"`, `"open tickets"`, `"tickets abiertos"`) while preserving negative lookaheads against non-logistics polysemic uses, and added corporate/carrier history and founding trivia rules to `_OUT_OF_DOMAIN_PATTERNS` so queries like `"whats the history of FedEx"` are deflected pre-execution.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added carrier corporate history/origin/founding patterns to `OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL`, ticket lookup verbs to `_OPERATIONAL_LOGISTICS_ACTIONS`, and open/pending/active ticket collocations with polysemy negative lookahead to `_IN_DOMAIN_LOGISTICS_CUES`. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | added test | Added `TestGuardrailTicketAndCarrierHistoryDomainScoping` covering 11 open/pending support ticket queries and 10 carrier history/founding trivia queries across `InputGuardrailValidator` and `FastIntentSemanticRouter`. |

## Diff Highlights (optional)

```python
# 1. Carrier History & Founding Deflection in _OUT_OF_DOMAIN_PATTERNS (OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL)
r"|\b(?:(?:history|origins?|foundation|founding|backstory)\s+of\s+(?:the\s+)?(?:[a-z0-9_-]+\s+){0,3}(?:fedex|ups|dhl|mrw|seur|usps|company|corporation|airline|carrier))\b"
r"|\b(?:(?:historia|origen|or[ií]genes|fundaci[oó]n)\s+(?:de|del|de\s+la)\s+(?:[a-z0-9ñáéíóú_-]+\s+){0,3}(?:fedex|ups|dhl|mrw|seur|usps|empresa|compa[ñn][ií]a))\b"
r"|\b(?:(?:who|when)\s+(?:founded|established|created|started)\s+(?:the\s+)?(?:[a-z0-9_-]+\s+){0,2}(?:fedex|ups|dhl|mrw|seur|usps|company))\b"
r"|\b(?:when\s+was\s+(?:the\s+)?(?:[a-z0-9_-]+\s+){0,2}(?:fedex|ups|dhl|mrw|seur|usps|company)\s+(?:founded|established|created|started|born|formed))\b"

# 2. Operational Ticket Lookup Cues in _IN_DOMAIN_LOGISTICS_CUES
r"|(?:(?:open|pending|active|unresolved|recent|closed|resolved|my|our|mis|nuestros)\s+(?:support\s+|incident\s+)?tickets?|support\s+tickets?|tickets?\s+(?:open|pending|active|unresolved|closed|resolved|abiertos?|pendientes?|activos?|cerrados?|resueltos?)|(?:mis|mis\s+[uú]ltimos)\s+tickets?)(?!\s*(?:#?\d+\s+)?(?:for|regarding|about|on|to)\s+(?:(?:the|my|a|an)\s+)?(?:concert|movie|cinema|musical|broadway|symphony|festival|theater|theatre|show|flight|train|bus|parking|speeding|traffic|lottery|museum|match|game|stadium|netflix|streaming|municipal|water\s+pipeline))"
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestGuardrailTicketAndCarrierHistoryDomainScoping::test_open_and_pending_support_ticket_queries_are_allowed` — Verifies English and Spanish open/pending support ticket queries return `action="allow"`, `input_category="in_domain"`, and `FastIntentSemanticRouter.classify(...) == "IN_DOMAIN"`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestGuardrailTicketAndCarrierHistoryDomainScoping::test_carrier_history_and_founding_trivia_queries_are_deflected` — Verifies English and Spanish carrier corporate history and founding trivia queries return `action="deflect"`, `input_category="out_of_domain"`, and `FastIntentSemanticRouter.classify(...) == "OUT_OF_DOMAIN"`.

## Local Verification

- Commands run: `python -m pytest tests/unit/test_agent_guardrails_input.py -q` → `301 passed in 2.04s`
- Manual checks: Verified all 100 adversarial queries (including concert, movie, speeding, Broadway, Netflix, and municipal water pipeline ticket queries) and 50 legitimate control queries pass without regression.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=guardrail-ticket-domain-scoping` to formally validate and record the verification report.
