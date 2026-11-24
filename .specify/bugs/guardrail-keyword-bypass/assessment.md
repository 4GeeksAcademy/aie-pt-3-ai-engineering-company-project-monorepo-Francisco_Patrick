# Bug Assessment: Guardrail Keyword-Matching Bypass via In-Domain Terminology

- **Slug**: guardrail-keyword-bypass
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> Users can bypass guardrail restrictions to obtain responses outside the company’s scope by using terms that belong to the corporate domain. The system does not analyze the context of the entire sentence; instead, it checks only for the presence of a specific keyword. If that keyword falls within the corporate domain—even if the user's actual query does not—the request passes the guardrail, and the agent provides a response that lies outside the company’s context.
> For example, asking “how tall is the FedEx CEO?” returns that information, even though it is unrelated to the company’s context.
> Asking “what is the meaning of the Order of the Phoenix?” passes the check because it contains the word “Phoenix.”
> Asking “which restaurant is closest to the warehouse?” also bypasses the guardrail.

## Symptom

Users can bypass input guardrail restrictions and obtain responses outside TrackFlow's corporate logistics scope by embedding single domain-associated keywords (e.g., carrier names like `"FedEx"`, generic nouns like `"order"`, or facility words like `"warehouse"`) into out-of-domain queries. The system evaluates isolated keyword occurrences rather than overall sentence intent and semantic context, allowing queries like `"how tall is the FedEx CEO?"`, `"what is the meaning of the Order of the Phoenix?"`, or `"which restaurant is closest to the warehouse?"` to return `action="allow"` and `input_category="in_domain"`.

When allowed, these queries bypass pre-execution deflection at Layer 1 and enter the downstream agent workflow. If vector search retrieves carrier, facility, or order policy chunks, the agent synthesizes answers outside the company's context; if no chunks qualify, it falls back to a knowledge refusal that treats the query as a legitimate TrackFlow operational inquiry rather than deflecting it at the boundary.

## Reproduction

1. In Python, run `InputGuardrailValidator.evaluate_input` on queries containing corporate domain keywords in out-of-domain contexts:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()

   # Case 1: Executive biography / physical traits query containing carrier name "FedEx"
   res1 = validator.evaluate_input("how tall is the FedEx CEO?")
   # Observed: res1.action == "allow", res1.input_category == "in_domain", res1.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res1.action == "deflect", res1.input_category == "out_of_domain", res1.reason_code == "OUT_OF_DOMAIN_DEFLECTION"

   # Case 2: Literary / pop-culture query containing noun "Order"
   res2 = validator.evaluate_input("what is the meaning of the Order of the Phoenix?")
   # Observed: res2.action == "allow", res2.input_category == "in_domain", res2.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res2.action == "deflect", res2.input_category == "out_of_domain", res2.reason_code == "OUT_OF_DOMAIN_DEFLECTION"

   # Case 3: Food / dining inquiry near facility containing keyword "warehouse"
   res3 = validator.evaluate_input("which restaurant is closest to the warehouse?")
   # Observed: res3.action == "allow", res3.input_category == "in_domain", res3.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res3.action == "deflect", res3.input_category == "out_of_domain", res3.reason_code == "OUT_OF_DOMAIN_DEFLECTION"
   ```

2. Send `"how tall is the FedEx CEO?"` through `SupportAgentService.query` or the REST API `POST /api/v1/agent/query`:
   - Observed: Layer 1 allows the query (`guardrail_action="allow"`). The system proceeds to RAG retrieval and generation or operational refusal, rather than rejecting the query at the input boundary.
   - Expected: Pre-execution deflection at Layer 1 returning `action="deflect"`, `failure_category="content"`, `input_category="out_of_domain"`, and the neutral deflection message redirecting the user to TrackFlow's logistics scope.

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:368-412` (`_IN_DOMAIN_LOGISTICS_CUES`):
  - Matches broad individual terms such as `fedex`, `order`, and `warehouse` using simple word boundary regexes (`\b(?:ups|fedex|...)\b`, `\b(?:order|orders|...)\b`, `\b(?:...|warehouse|...)\b`).
- `services/api/application/services/agent_guardrails.py:326-352` (`_OUT_OF_DOMAIN_PATTERNS`):
  - Contains only narrow patterns for weather and geography/trivia (e.g. `capital of`, `population of`, `photosynthesis`). It lacks patterns for dining/restaurants, entertainment/literature/movies, executive biographies, or personal traits (height, age, net worth).
- `services/api/application/services/agent_guardrails.py:638-666` (`InputGuardrailValidator.evaluate_input`):
  - Evaluates `is_direct_in_domain = bool(_IN_DOMAIN_TRACKFLOW_CUE.search(cleaned) or ...)` at Tier 5 without verifying semantic intent or validating whether the query combines in-domain keywords with incompatible out-of-domain predicates (e.g. restaurant recommendations, movie/book trivia, executive physical attributes).
- `services/api/application/services/agent_workflow.py:440-498` (`intake_node`):
  - Directly trusts `input_eval.action == "allow"` and proceeds to route the out-of-domain query into RAG retrieval and synthesis nodes.

## Root Cause Hypothesis

`InputGuardrailValidator.evaluate_input` relies on a two-step lexical pattern pipeline that is vulnerable to keyword-stuffing and contextual bypasses:
1. `_OUT_OF_DOMAIN_PATTERNS` (Tier 3) only matches a small, rigid set of subjects (weather, capitals, photosynthesis, jokes). Non-logistics queries regarding dining/restaurants, popular fiction/literature, or executive biographies do not match Tier 3.
2. In Tier 5, `_IN_DOMAIN_LOGISTICS_CUES.search(cleaned)` searches for any standalone occurrence of common logistics keywords (such as `"fedex"`, `"order"`, `"warehouse"`). Because words like `"order"` have dual everyday/literary meanings, and carrier/facility names can appear inside unrelated personal/local queries, any query containing one of these words is unconditionally granted `action="allow"` and `input_category="in_domain"`.
Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Contextual Incompatibility & Negative Out-of-Domain Pattern Expansion**:
   - Add negative patterns to `_OUT_OF_DOMAIN_PATTERNS` for common out-of-scope query intents, including:
     - Dining, food, and hospitality: `\b(?:restaurant|restaurants|cafe|cafeteria|bar|food|dinner|lunch|breakfast|eat|dining|restaurante|comida|cenar|almorzar)\b`.
     - Entertainment, pop culture, and fiction: `\b(?:order\s+of\s+the\s+phoenix|harry\s+potter|movie|film|actor|actress|pel[ií]cula|libro|novela|canci[oó]n|song|band|album)\b`.
     - Celebrity, executive, or biographical trivia: `\b(?:how\s+tall\s+is|height\s+of|age\s+of|how\s+old\s+is|net\s+worth\s+of|salary\s+of|cu[aá]nto\s+mide|altura\s+de|edad\s+de|qui[eé]n\s+es\s+el\s+ceo\s+de)\b`.
   - Ensure negative out-of-scope predicates override superficial presence of logistics keywords (e.g. `"restaurant"` + `"warehouse"`, `"how tall"` + `"FedEx"`).
2. **Context-Aware In-Domain Disambiguation**:
   - Disambiguate polysemous keywords like `"order"`: require logistics context (e.g., `"order status"`, `"my order"`, `"order #\d+"`, `"place an order"`, `"order tracking"`, or paired with purchase/shipping terms) rather than bare unanchored `"order"` matching literary titles or idioms like `"Order of the Phoenix"` or `"in order to"`.
   - For facility and carrier keywords (`warehouse`, `FedEx`, `UPS`), ensure the inquiry pertains to logistics operations (status, dispatch, drop-off, delivery, tracking, pickup, storage) rather than surrounding points of interest (restaurants, hotels, sights) or personal executive trivia.

**Alternatives**:
- *Alternative 1*: Integrate a lightweight local classifier (e.g., fine-tuned FastText or embeddings-based cosine similarity against domain intent centroids) to evaluate semantic sentence intent rather than regex matching. *Trade-off*: Introduces additional dependency and vector scoring overhead in Layer 1, though it provides broader semantic generalization.
- *Alternative 2*: Let Layer 1 pass keyword hits, but introduce a semantic boundary validation check in `intake_node` before RAG execution. *Trade-off*: Violates Layer 1 pre-execution design principles and fails to block invalid inputs at the initial guardrail interface.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- In `test_agent_guardrails_input.py`:
  - Add test cases under `test_out_of_domain_queries_are_deflected_with_neutral_message`:
    - `"how tall is the FedEx CEO?"` -> `action="deflect"`, `input_category="out_of_domain"`
    - `"what is the meaning of the Order of the Phoenix?"` -> `action="deflect"`, `input_category="out_of_domain"`
    - `"which restaurant is closest to the warehouse?"` -> `action="deflect"`, `input_category="out_of_domain"`
    - Bilingual variants (e.g., `"¿cuánto mide el CEO de FedEx?"`, `"¿qué restaurante queda más cerca del almacén?"`).
  - Verify that legitimate logistics queries containing those words continue to pass with `action="allow"`:
    - `"When was my FedEx order shipped?"`
    - `"What is the address of the Los Angeles warehouse?"`
    - `"I want to check the status of my order #45821."`
    - `"How does FedEx handle lost packages?"`

## Risks & Considerations

- **False Positive Risk on Legitimate Support Queries**: Tightening keyword patterns or adding out-of-domain filters must not inadvertently block valid operational requests. For instance, questions like `"Can I pick up my order at the warehouse?"` or `"Is FedEx delivering my shipment today?"` must remain allowed.
- **Polysemy of Common English Words**: Words like `"order"` appear in non-logistics phrases (`"in order to"`, `"out of order"`, `"Order of the Phoenix"`). Disambiguating `"order"` requires careful regex structuring or collocation checks.

## Open Questions

- None.
