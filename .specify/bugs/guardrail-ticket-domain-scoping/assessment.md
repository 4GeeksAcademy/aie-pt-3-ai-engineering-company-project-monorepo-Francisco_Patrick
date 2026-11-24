# Bug Assessment: Guardrail False Negatives on Open Ticket Queries and False Positive Bypass on Carrier History

- **Slug**: guardrail-ticket-domain-scoping
- **Created**: 2026-11-24
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> Guardrails is rejecting valid questions like open tickets question and is allowing question out of the company context like "whats the history of FedEx".

## Symptom

Layer 1 Input Guardrails (`InputGuardrailValidator` and `FastIntentSemanticRouter`) exhibit two complementary domain-boundary classification defects:

1. **False Negative (Deflecting Valid Support Queries)**:
   Legitimate customer and internal support inquiries regarding support tickets (e.g., `"can you check open tickets"`, `"do I have any open tickets?"`, `"what are my open tickets?"`, `"show my open tickets"`, `"open tickets"`, `"check open tickets"`, `"list my open tickets"`, or Spanish equivalents like `"¿tengo tickets abiertos?"`) are incorrectly deflected to:
   - `action="deflect"`
   - `decision="deflect"`
   - `input_category="out_of_domain"`
   - `reason_code="OUT_OF_DOMAIN_DEFLECTION"`
   
   Expected behavior: The query should be recognized as an in-domain TrackFlow operational inquiry (`action="allow"`, `input_category="in_domain"`, `reason_code="IN_DOMAIN_ALLOWED"`), proceeding to `agent_workflow` where `_extract_ticket_tool_input` parses `status="open"` to query `IncidentSupportTicketToolAdapter`.

2. **False Positive (Bypassing Guardrails with Out-of-Domain Carrier History/Trivia)**:
   Inquiries concerning general corporate history or third-party carrier trivia (e.g., `"whats the history of FedEx"`, `"What is the history of FedEx?"`, `"tell me the history of FedEx"`, `"when was FedEx established"`, `"who founded FedEx"`) bypass Layer 1 and are erroneously approved as in-domain:
   - `action="allow"`
   - `decision="allow"`
   - `input_category="in_domain"`
   - `reason_code="IN_DOMAIN_ALLOWED"`

   Expected behavior: The query is unrelated to TrackFlow's commercial shipment tracking, return policies/SLAs, or delivery incident procedures. It should be deflected pre-execution (`action="deflect"`, `input_category="out_of_domain"`).

## Reproduction

Run the following test using `InputGuardrailValidator` from `services/api`:

```python
from application.services.agent_guardrails import InputGuardrailValidator

validator = InputGuardrailValidator()

# 1. Open Ticket Queries (Observed: Deflected; Expected: Allowed)
ticket_queries = [
    "can you check open tickets",
    "do I have any open tickets?",
    "what are my open tickets?",
    "show my open tickets",
    "open tickets",
    "check open tickets",
    "list my open tickets",
    "tickets abiertos",
    "consultar tickets abiertos",
]

for q in ticket_queries:
    res = validator.evaluate_input(q)
    # Observed: res.action == "deflect", res.reason_code == "OUT_OF_DOMAIN_DEFLECTION"
    # Expected: res.action == "allow", res.input_category == "in_domain"

# 2. FedEx History and Corporate Trivia Queries (Observed: Allowed; Expected: Deflected)
history_queries = [
    "whats the history of FedEx",
    "What is the history of FedEx?",
    "tell me the history of FedEx",
    "who founded FedEx",
    "when was FedEx established",
    "tell me about the origin of FedEx",
]

for q in history_queries:
    res = validator.evaluate_input(q)
    # Observed: res.action == "allow", res.reason_code == "IN_DOMAIN_ALLOWED"
    # Expected: res.action == "deflect", res.input_category == "out_of_domain"
```

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:606`:
  In `_IN_DOMAIN_LOGISTICS_CUES`, third-party carrier names are matched as bare unconstrained tokens:
  ```python
  r"|\b(?:ups|fedex|dhl|mrw|seur|usps)\b"
  ```
  Any query mentioning "FedEx" (even in non-logistics contexts such as history, trivia, stock valuation, or fleet trivia) unconditionally triggers this regex cue unless matched by an earlier out-of-domain filter.

- `services/api/application/services/agent_guardrails.py:641`:
  In `_IN_DOMAIN_LOGISTICS_CUES`, tickets are strictly constrained to:
  ```python
  r"|\b(?:(?:delivery|shipping|logistics|cx|trackflow)\s+tickets?|support\s+ticket\s+(?:inc[-_]\d+|tf[-_]\d+|\bfor\s+(?:my\s+)?(?:shipment|order|package|delivery|return|refund|freight))|tickets?\s+de\s+(?:soporte\s+de\s+trackflow|soporte\s+log[ií]stico|entrega|env[ií]o))\b"
  ```
  Common operational variations such as `"open tickets"`, `"check tickets"`, `"show tickets"`, `"active tickets"`, `"my tickets"`, `"support tickets"`, `"tickets abiertos"`, and `"tickets pendientes"` do not match.

- `services/api/application/services/agent_guardrails.py:512-530`:
  `_OPERATIONAL_LOGISTICS_ACTIONS` regex matches verbs for tracking, cancellation, and returns, but completely omits ticket review actions (e.g., `check open tickets`, `list my tickets`, `consultar tickets`).

- `services/api/application/services/agent_guardrails.py:327-500`:
  `_OUT_OF_DOMAIN_PATTERNS` lacks coverage for company history, corporate trivia, founders, or origins (`"history of <company>"`, `"when was <company> founded"`, `"origin of <carrier>"`), allowing carrier trivia to slip past Tier 3 deflection.

## Root Cause Hypothesis

The root cause consists of an asymmetry introduced during previous polysemic keyword decoupling:
1. To guard against polysemic bypasses (such as "concert ticket", "movie ticket", "speeding ticket"), `_IN_DOMAIN_LOGISTICS_CUES` overly restricted `ticket` to require compound phrases like `delivery tickets` or `shipping tickets`. This excluded standard customer support phrasing (`open tickets`, `my tickets`, `tickets abiertos`), while `_OPERATIONAL_LOGISTICS_ACTIONS` and `_ORDER_REFERENCE_PATTERNS` failed to recognize ticket status inquiries lacking a specific numeric ID.
2. Conversely, carrier names (`ups`, `fedex`, `dhl`, `mrw`, `seur`, `usps`) remained unconstrained bare tokens in `_IN_DOMAIN_LOGISTICS_CUES`. Without required operational collocations (e.g., shipping, delivery, transit, tracking) and with no out-of-domain pattern targeting company/carrier corporate history or trivia (`history of FedEx`, `when was FedEx founded`), inquiries about the history of FedEx immediately match `_IN_DOMAIN_TRACKFLOW_CUE` and are allowed.

Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Support Ticket Intent Recognition**:
   - Update `_IN_DOMAIN_LOGISTICS_CUES` (around line 641) to allow operational ticket collocations such as:
     - `\b(?:(?:open|pending|active|unresolved|recent|all|my|mis)\s+(?:support\s+)?tickets?|support\s+tickets?|tickets?\s+(?:open|pending|active|unresolved|abiertos?|pendientes?|de\s+soporte)|(?:mis|mis\s+últimos|mis\s+ultimos)\s+tickets?)\b`
   - Update `_OPERATIONAL_LOGISTICS_ACTIONS` (around line 512) to include ticket lookup actions:
     - `\b(?:check|view|show|list|get|consultar|ver|listar)\s+(?:(?:my|the|all|open|pending|active|mis|los|estos)\s+)?(?:support\s+)?tickets?\b`
   - Ensure non-logistics polysemic uses ("movie tickets", "concert tickets", "speeding ticket") remain safely deflected.

2. **Carrier History & Corporate Trivia Deflection**:
   - Add an out-of-domain pattern or expand `_OUT_OF_DOMAIN_PATTERNS` to deflect corporate history, origins, founding, and general company trivia:
     - `r"\b(?:history\s+of|historia\s+de|origins?\s+of|origen\s+de|who\s+founded|qui[eé]n\s+fund[oó]|when\s+was\s+[a-z0-9_-]+\s+(?:founded|established|created|started)|cu[aá]ndo\s+(?:se\s+fund[oó]|fue\s+fundad[oa])|foundation\s+of|fundaci[oó]n\s+de)\s+(?:[a-z0-9_-]+\s+){0,3}(?:fedex|ups|dhl|mrw|seur|usps|company|empresa)\b"`
     - Alternatively, ensure `OUT_OF_DOMAIN_ACADEMIC_AND_HISTORICAL` or a dedicated `OUT_OF_DOMAIN_CORPORATE_OR_CARRIER_TRIVIA` categorizes inquiries into company founding, corporate histories, and executive trivia.
   - Refine carrier keywords in `_IN_DOMAIN_LOGISTICS_CUES` to prevent bare unconstrained matching from overriding out-of-domain signals.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Unit test cases in `test_agent_guardrails_input.py`:
  - Verify that queries asking for open/pending tickets (`"can you check open tickets"`, `"do I have any open tickets?"`, `"what are my open tickets?"`, `"show my open tickets"`, `"tickets abiertos"`) are classified as `in_domain` (`action="allow"`).
  - Verify that queries asking about the history or founding of carriers (`"whats the history of FedEx"`, `"tell me the history of FedEx"`, `"when was FedEx founded"`, `"who founded FedEx"`, `"historia de FedEx"`) are classified as `out_of_domain` (`action="deflect"`).
  - Ensure adversarial polysemic ticket tests ("concert tickets", "movie tickets", "speeding ticket") continue to deflect.
  - Ensure legitimate operational carrier queries ("When was my FedEx order shipped?", "Can I ship with FedEx?") remain allowed.

## Risks & Considerations

- **Polysemy Guard**: When allowing phrases like "open tickets" or "check tickets", ensure words like "movie ticket", "traffic ticket", "concert ticket" or "plane ticket" are not inadvertently admitted.
- **Carrier Operational Queries**: Legitimate carrier tracking and delivery inquiries ("When was my FedEx package delivered?", "Is FedEx experiencing delays in Los Angeles?") must not be blocked.

## Open Questions

- None. The distinction between commercial support inquiries (checking open tickets) and general carrier history/trivia (history of FedEx) is unambiguous.
