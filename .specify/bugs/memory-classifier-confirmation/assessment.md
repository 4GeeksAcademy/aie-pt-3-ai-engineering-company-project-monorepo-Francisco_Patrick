# Bug Assessment: Memory Intent Classifier Confirmation and Instruction Boundary Fix

- **Slug**: memory-classifier-confirmation
- **Created**: 2026-11-21
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> There are two issues:
>
> * The classifier doesn't accept a natural confirmation, because it classifies a simple "Yes" or "Sí" as ambiguous and discards the proposal, even though the agent just asked, "Would you like me to remember this rule?"
> * It's classifying "Yes, remember to check the stock tomorrow" as an `approve` and saving the pending rule, even when the user is asking for something else.
>
> Require an unambiguous, brief confirmation (yes/sí/no) and reject "yes + new instruction," adding tests for both cases if needed.

## Symptom

1. **Natural brief confirmation rejected / discarded**: When an agent prompts `"Would you like me to remember this rule for future sessions?"`, a concise affirmative response such as `"Yes"` or `"Sí"` is classified as `unrelated_or_ambiguous` instead of `approve`. Consequently, the pending memory proposal is discarded rather than saved.
2. **False positive approval on compound instruction**: When a user replies with `"Yes, remember to check the stock tomorrow"`, the classifier matches `"Yes, remember"` as an approval phrase, returning `intent="approve"` and extracting `"to check the stock tomorrow"` as a residual query. This causes the pending operational memory rule to be approved and persisted into memory, even though the user was giving a task directive ("remember to check the stock tomorrow") rather than confirming the proposed rule.

## Reproduction

1. In Python, instantiate `UserIntentClassifier`:
   ```python
   from application.services.memory_service import UserIntentClassifier
   classifier = UserIntentClassifier()
   summary = "SEUR no longer covers rural Zaragoza; use local carriers."
   ```
2. Test natural brief affirmative confirmation:
   ```python
   res1 = classifier.classify("Yes", summary)
   # Observed: res1.intent == "unrelated_or_ambiguous"
   # Expected: res1.intent == "approve"

   res2 = classifier.classify("Sí", summary)
   # Observed: res2.intent == "unrelated_or_ambiguous"
   # Expected: res2.intent == "approve"
   ```
3. Test natural brief negative rejection:
   ```python
   res3 = classifier.classify("No", summary)
   # Observed: res3.intent == "unrelated_or_ambiguous"
   # Expected: res3.intent == "reject"
   ```
4. Test "yes + new instruction":
   ```python
   res4 = classifier.classify("Yes, remember to check the stock tomorrow", summary)
   # Observed: res4.intent == "approve", res4.residual_query == "to check the stock tomorrow"
   # Expected: res4.intent != "approve" (rejected or classified as unrelated_or_ambiguous, ensuring the pending rule is NOT saved)
   ```

## Suspected Code Paths

- `services/api/application/services/memory_service.py:245-253` — `_APPROVE_PREFIX_PATTERN`: Requires an explicit action verb (`remember|save|store|keep|confirm|approve|guarda|...`) directly after affirmative tokens. Standalone affirmative words like `"Yes"` or `"Sí"` fail to match. Additionally, matches `"remember"` followed by arbitrary infinitives/clauses like `"to check the stock"`.
- `services/api/application/services/memory_service.py:254-261` — `_REJECT_PREFIX_PATTERN`: Requires an explicit rejection verb phrase (`do not save|don't remember|no lo guardes|...`). Standalone negative tokens like `"No"` fail to match.
- `services/api/application/services/memory_service.py:263-266` — `_RESIDUAL_CONNECTOR_PATTERN`: Connector is optional (`(?:and\s+|also\s+|y\s+|adem[aá]s\s+)?`), allowing trailing phrases like `"to check the stock tomorrow"` to be cleanly extracted after partial prefix matches.
- `services/api/application/services/memory_service.py:361-372` — `UserIntentClassifier.classify()`: Matches approve prefix and extracts residual query without validating whether the user gave a new instruction instead of an unambiguous rule confirmation.
- `services/api/tests/unit/test_intent_classification.py:28-60` — Existing unit test suite lacks test cases for standalone brief confirmations/rejections (`"Yes"`, `"Sí"`, `"No"`) and positive-negative boundaries for instructions like `"Yes, remember to check the stock tomorrow"`.

## Root Cause Hypothesis

**Confidence: High**

The regex pattern `_APPROVE_PREFIX_PATTERN` was formulated under the assumption that user confirmations always repeat the verb phrase (e.g., `"Yes, please remember that rule"` or `"Confirmed, save that to memory"`). The grammar in `_APPROVE_PREFIX_PATTERN` does not allow bare affirmatives (`"Yes"`, `"Sí"`, `"Yes, please"`, `"Sí, por favor"`), causing the classifier to drop into the fallback `unrelated_or_ambiguous` branch. Similarly, `_REJECT_PREFIX_PATTERN` mandates phrases like `"do not save"` and misses bare `"No"`.

Furthermore, `_APPROVE_PREFIX_PATTERN` treats `"remember"` as a confirmation keyword without checking if it introduces an imperative infinitive clause (`"remember to <do something>"`). Because `_APPROVE_PREFIX_PATTERN` matched `"Yes, remember"` and the residual regex greedily trimmed the prefix, the classifier interpreted `"Yes, remember to check the stock tomorrow"` as an approval of the pending proposal with a residual query, inadvertently committing an unrelated rule into persistent memory.

## Proposed Remediation

**Preferred**:
1. **Support Unambiguous Brief Confirmations & Rejections**:
   - Update `_APPROVE_PREFIX_PATTERN` (or introduce a dedicated exact-match pattern) to recognize standalone brief affirmative confirmations in English and Spanish, including optional polite markers:
     `r"^\s*(?:yes|yeah|yep|s[ií]|claro|por\s+supuesto)(?:\s*,?\s*(?:please|por\s+favor))?[\s.!]*$"`
   - Update `_REJECT_PREFIX_PATTERN` (or introduce a dedicated exact-match pattern) to recognize standalone brief negative rejections:
     `r"^\s*(?:no|nope|no\s+thanks|no\s+gracias|no\s+por\s+favor)(?:\s*,?\s*(?:please|por\s+favor))?[\s.!]*$"`
2. **Disallow "Yes + New Instruction" as Proposal Approval**:
   - Explicitly differentiate memory-rule confirmation (e.g., `"Yes, remember this rule"`, `"Yes, save it"`, `"Sí, guarda esa regla"`) from task instructions directed at the agent (e.g., `"remember to <action>"` or `"recuerda <acción>"`).
   - Ensure expressions of the form `"remember to ..."` or `"recuerda ..."` (introducing a future operational action or instruction) are rejected from the approval category and classified as either `unrelated_or_ambiguous` (with the prompt as a query/instruction to execute) or `reject`, ensuring the pending memory rule is NOT approved or saved.
   - For multi-intent confirmation (if permitted under FR-015), enforce that approval only triggers if the confirmation clause unambiguously targets the pending memory/rule (e.g. `"Yes save that rule, and check stock..."`), strictly rejecting sentences where the affirmative precedes an instruction rather than an explicit rule confirmation.
3. **Comprehensive Unit & Integration Test Coverage**:
   - Add unit tests in `services/api/tests/unit/test_intent_classification.py` for:
     - Standalone `"Yes"`, `"Sí"`, `"Si"`, `"Yes please"`, `"Sí, por favor"`, `"Yeah"`, `"Yep"` classifying as `approve`.
     - Standalone `"No"`, `"No."`, `"No thanks"`, `"No gracias"` classifying as `reject`.
     - Instruction inputs such as `"Yes, remember to check the stock tomorrow"` ensuring they do NOT classify as `approve` and the pending rule is NOT saved.

**Alternatives**:
- Strict Whitelist Confirmation: Only allow exact brief confirmations (`"yes"`, `"sí"`, `"no"`, `"yes please"`, `"no thanks"`) or explicit rule references (`"yes, remember this rule"`). Any input combining an affirmative with operational verbs or instructions (`"remember to..."`, `"check..."`) is strictly treated as an operational topic shift (`unrelated_or_ambiguous`), discarding the pending memory rule and routing the operational query.

**Files likely to change**:
- `services/api/application/services/memory_service.py`
- `services/api/tests/unit/test_intent_classification.py`
- `services/api/tests/integration/test_agent_memory_lifecycle.py`

**Tests to add or update**:
- `test_classifies_brief_natural_confirmations`: assert `"Yes"`, `"Sí"`, `"Yes please"`, `"Sí, por favor"` return `intent == "approve"`.
- `test_classifies_brief_natural_rejections`: assert `"No"`, `"No."`, `"No thanks"`, `"No, gracias"` return `intent == "reject"`.
- `test_rejects_yes_plus_new_instruction_as_approval`: assert `"Yes, remember to check the stock tomorrow"` and similar commands do NOT return `intent == "approve"` and do not cause memory persistence.

## Risks & Considerations

- **Audit Log Consistency**: Standalone `"No"` must record an audit entry with `event_type="rejected"` rather than `"discarded"`, which properly reflects operator rejection.
- **FR-015 Compatibility**: Ensure that legitimate multi-intent approvals that explicitly reference the rule (`"Yes save that rule, and what is the current stock of SKU-100?"`) continue to work without false-rejection, while preventing non-rule directives (`"remember to..."`) from hijacking the approval path.

## Open Questions

- None blocking.
