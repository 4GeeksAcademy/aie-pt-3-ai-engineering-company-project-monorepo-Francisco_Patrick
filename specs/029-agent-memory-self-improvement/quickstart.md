# Quickstart Validation Guide: Agent Memory & Self-Improvement

**Feature**: `029-agent-memory-self-improvement`  
**Date**: 2026-11-21  
**Status**: Ready for Verification  

This guide provides deterministic, runnable end-to-end scenarios to validate the agent memory subsystem. Refer to [data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/029-agent-memory-self-improvement/data-model.md) and [contracts/agent-memory-api.yaml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/029-agent-memory-self-improvement/contracts/agent-memory-api.yaml) for entity structures and endpoint contracts.

---

## Prerequisites & Environment Setup

1. **Working Directory & Python Environment**:
   ```bash
   cd services/api
   uv sync
   ```

2. **Verify Baseline Test Suite**:
   ```bash
   uv run pytest tests/unit/test_agent_workflow.py
   ```

3. **Temporary Persistence Setup**:
   The validation suite uses isolated in-memory or test-scoped persistent databases (`agent_memory_test.json`), ensuring static Qdrant collections (`trackflow_knowledge`) are neither targeted nor altered.

---

## Scenario 1: Single-Call Memory Proposal on Carrier Route Correction

**Goal**: Prove that an operator providing an operational route correction receives an answer acknowledging the rule AND a structured proposal in the same turn without secondary LLM round-trips.

**Execution Command**:
```bash
uv run python -m pytest tests/integration/test_agent_memory_lifecycle.py -k "test_single_call_carrier_proposal"
```

**Expected Outcome**:
- Response contains conversational acknowledgment of Zaragoza carrier coverage update.
- Response appends confirmation prompt: `"Would you like me to remember this rule for future sessions?"`
- Response schema contains non-null `memory_proposal`:
  - `category`: `"carrier_rule"`
  - `target_entity`: `"SEUR"`
  - `country_code`: `"ES"`
  - `status`: `"pending"`
- Persistent memory records count is `0` (write deferred until operator confirms).
- Total turn execution time overhead < 100ms.

---

## Scenario 2: Explicit Intent Classification — Approval & Cross-Session Recall

**Goal**: Confirm that explicit user approval commits the rule to persistent memory, and a new session immediately recalls and applies this rule.

**Execution Command**:
```bash
uv run python -m pytest tests/integration/test_agent_memory_lifecycle.py -k "test_approve_and_cross_session_recall"
```

**Expected Outcome**:
1. **Turn 1 (Approval)**:
   - User inputs: `"Yes, please remember that rule for SEUR."`
   - Intent classified as `approve` (confidence > 0.90).
   - Proposal status transitions to `approved`.
   - Record created in `PersistentMemoryRecord` with `category="carrier_rule"`, `target_entity="SEUR"`, `country_code="ES"`.
   - Immutable audit log entry logged with `event_type="approved"`, `resulting_action="memory_persisted"`.
2. **Turn 2 (New Session Recall)**:
   - Client starts a fresh session (`thread_id="session_new_2"`) with inquiry: `"What carrier should I assign for rural shipments in Zaragoza?"`
   - Agent recalls persisted SEUR constraint without querying or modifying Qdrant `trackflow_knowledge`.
   - Agent recommends alternative local carrier and notes SEUR discontinued rural coverage in Zaragoza.
   - `recalled_memories` in response includes the stored SEUR rule.

---

## Scenario 3: Safe Default Discard on Ambiguity or Topic Shift

**Goal**: Ensure ambiguous phrases or abrupt topic switches safely discard pending proposals with zero persistent storage mutation.

**Execution Command**:
```bash
uv run python -m pytest tests/integration/test_agent_memory_lifecycle.py -k "test_safe_default_discard_on_topic_shift"
```

**Expected Outcome**:
- When proposal is pending and user asks: `"Can you check current stock for SKU-401?"`
- Intent classifier returns `unrelated_or_ambiguous`.
- Proposal status transitions to `discarded`.
- Persistent memory record count remains unchanged (`0` records written).
- Audit log records `event_type="discarded"`, `resulting_action="proposal_discarded"`.
- Residual query (`"Can you check current stock for SKU-401?"`) continues downstream to `inventory_tool` in the exact same turn without blocking the user.

---

## Scenario 4: Anti-Poisoning & Sensitive Data Filtering

**Goal**: Verify that forbidden sensitive data (end-consumer B2C physical address or warehouse floor layout) is blocked from proposal generation and persistent storage.

**Execution Command**:
```bash
uv run python -m pytest tests/unit/test_memory_guardrails.py
```

**Test Inputs & Expected Rejections**:
1. **Sensitive B2C Address**:
   - Input: `"Remember that customer John Doe lives at Calle Mayor 14, 3B, Zaragoza, deliver after 5pm."`
   - Verdict: `allowed=False`, `violation_code="SENSITIVE_LOCATION"`.
   - Output: No proposal offered; zero records written.
2. **Internal Warehouse Layout**:
   - Input: `"Always store pallet overflow in Aisle 4 past security checkpoint B."`
   - Verdict: `allowed=False`, `violation_code="WAREHOUSE_PHYSICAL_SECURITY"`.
   - Output: No proposal offered; zero records written.
3. **One-Off Complaint**:
   - Input: `"Package XJ4471 arrived torn."`
   - Verdict: `allowed=False`, `violation_code="ONE_OFF_COMPLAINT"`.
   - Output: No proposal offered; zero records written.

---

## Scenario 5: Memory Consolidation per Carrier + Country

**Goal**: Verify that multiple approved carrier updates for the same carrier and country consolidate into a clean profile rather than fragmented duplicate entries.

**Execution Command**:
```bash
uv run python -m pytest tests/unit/test_memory_consolidation.py
```

**Expected Outcome**:
- Submitting two updates for SEUR in Spain (update 1: rural Zaragoza coverage discontinued; update 2: max weight constraint 30kg).
- Both updates approved.
- Querying `/api/v1/agent/memory/carriers/SEUR?country_code=ES` returns a single `ConsolidatedCarrierProfile`:
  - `carrier`: `"SEUR"`
  - `country_code`: `"ES"`
  - `active_rules`: `["SEUR rural Zaragoza discontinued; local carriers required", "Max weight constraint 30kg"]`
  - Total entries: 1 consolidated profile with 2 aggregated rules.

---

## Scenario 6: Strict Storage Isolation Verification

**Goal**: Cryptographically / structurally verify that Qdrant vector database (`trackflow_knowledge`) remains 100% read-only and point count is identical before and after memory lifecycles.

**Execution Command**:
```bash
uv run python -m pytest tests/integration/test_memory_storage_isolation.py
```

**Expected Outcome**:
- Initial Qdrant `trackflow_knowledge` point count recorded ($N$).
- 10 memory proposals generated, 5 approved, 5 discarded.
- Post-run Qdrant `trackflow_knowledge` point count queried ($N$).
- Delta: $\Delta = 0$ points added, updated, or removed in Qdrant.
- All persistent memories strictly stored in `agent_memory` persistence adapter.
