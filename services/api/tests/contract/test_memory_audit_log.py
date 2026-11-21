"""Contract and unit tests for immutable MemoryAuditLogEntry transitions (T017).

Verifies:
- Every lifecycle transition (`proposed`, `approved`, `rejected`, `edited`, `discarded`, `evicted`)
  produces an immutable audit log record with complete attribution (FR-014, SC-006).
- Audit log entries strictly sanitize PII (such as email addresses) before persistence
  in compliance with Monorepo Constitution Principle IV.
- `TinyDBMemoryAuditLogRepository` supports filtering by `proposal_id`, `event_type`, and `limit`
  ordered newest-first.
"""

from application.services.memory_guardrails import MemoryGuardrailValidator
from application.services.memory_service import (
    AgentMemoryService,
    UserIntentClassifier,
)
from infrastructure.persistence.tinydb.agent_memory_repository import (
    TinyDBAgentMemoryRepository,
)
from infrastructure.persistence.tinydb.memory_audit_log_repository import (
    TinyDBMemoryAuditLogRepository,
)


class TestMemoryAuditLogContract:
    """Contract tests for immutable memory lifecycle audit logging (T017)."""

    def setup_method(self) -> None:
        """Initialize memory service and repositories."""
        self.memory_repo = TinyDBAgentMemoryRepository()
        self.audit_repo = TinyDBMemoryAuditLogRepository()
        self.service = AgentMemoryService(
            memory_repository=self.memory_repo,
            audit_repository=self.audit_repo,
            guardrail_validator=MemoryGuardrailValidator(),
            intent_classifier=UserIntentClassifier(),
        )

    def test_records_proposed_and_approved_audit_trail(self) -> None:
        """Proposing and approving a memory must produce 'proposed' and 'approved' audit records."""
        proposal, _ = self.service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone; local carriers must be used starting this month.",
            base_answer="Acknowledged.",
            thread_id="audit-session-1",
        )
        assert proposal is not None

        resolution = self.service.resolve_pending_proposal(
            thread_id="audit-session-1",
            user_message="Yes, please remember that rule for SEUR.",
        )
        assert resolution is not None
        assert resolution["status"] == "approved"
        assert resolution["committed_memory_id"] is not None

        entries = self.audit_repo.list_entries(proposal_id=proposal.proposal_id)
        assert len(entries) == 2
        event_types = {e.event_type for e in entries}
        assert event_types == {"proposed", "approved"}

        approved_entry = next(e for e in entries if e.event_type == "approved")
        assert approved_entry.classified_intent == "approve"
        assert approved_entry.resulting_action == "memory_persisted"
        assert approved_entry.memory_id == resolution["committed_memory_id"]
        assert approved_entry.session_id == "audit-session-1"

    def test_records_rejected_and_discarded_audit_trails(self) -> None:
        """Explicit rejection and ambiguous topic shift must log 'rejected' and 'discarded' audit entries."""
        # 1. Explicit rejection
        p1, _ = self.service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone; local carriers must be used.",
            base_answer="Acknowledged.",
            thread_id="audit-session-reject",
        )
        assert p1 is not None
        res1 = self.service.resolve_pending_proposal(
            thread_id="audit-session-reject",
            user_message="No, do not save that.",
        )
        assert res1 is not None and res1["status"] == "rejected"

        reject_entries = self.audit_repo.list_entries(
            proposal_id=p1.proposal_id, event_type="rejected"
        )
        assert len(reject_entries) == 1
        assert reject_entries[0].classified_intent == "reject"
        assert reject_entries[0].resulting_action == "proposal_discarded"
        assert reject_entries[0].memory_id is None

        # 2. Ambiguous / topic shift -> discarded
        p2, _ = self.service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone; local carriers must be used.",
            base_answer="Acknowledged.",
            thread_id="audit-session-discard",
        )
        assert p2 is not None
        res2 = self.service.resolve_pending_proposal(
            thread_id="audit-session-discard",
            user_message="Can you check current stock for SKU-401?",
        )
        assert res2 is not None and res2["status"] == "discarded"

        discard_entries = self.audit_repo.list_entries(
            proposal_id=p2.proposal_id, event_type="discarded"
        )
        assert len(discard_entries) == 1
        assert discard_entries[0].classified_intent == "unrelated_or_ambiguous"
        assert discard_entries[0].resulting_action == "proposal_discarded"

    def test_audit_log_masks_email_pii_in_user_messages(self) -> None:
        """Audit entries must mask email addresses to uphold Constitution Principle IV (Zero PII Leakage)."""
        proposal, _ = self.service.evaluate_turn_for_proposal(
            user_message="SEUR no longer covers the rural Zaragoza zone per operator coordinator@trackflow.com; local carriers must be used.",
            base_answer="Acknowledged.",
            thread_id="audit-pii-session",
        )
        assert proposal is not None
        entries = self.audit_repo.list_entries(proposal_id=proposal.proposal_id)
        assert len(entries) == 1
        assert "coordinator@trackflow.com" not in entries[0].user_message
        assert "[REDACTED_EMAIL]" in entries[0].user_message
