"""Unit tests for Carrier + Country Memory Consolidation and Bounded Growth (T032).

Verifies Quickstart Scenario 5 and FR-016:
- Multiple approved carrier updates for the same `(carrier, country_code)` consolidate
  into a unified `ConsolidatedCarrierProfile` without duplicate rules.
- Carrier profiles strictly enforce the maximum 20 active constraints cap (`MAX_CONSOLIDATED_CARRIER_RULES = 20`),
  evicting/deactivating the oldest rules when exceeded.
- Recurrent incident contexts receive a default 14-day TTL and are evicted cleanly when expired.
"""

from datetime import datetime, timedelta, timezone

from application.services.memory_guardrails import MemoryGuardrailValidator
from application.services.memory_service import (
    AgentMemoryService,
    UserIntentClassifier,
)
from domain.agent.entities import PersistentMemoryRecord
from infrastructure.persistence.tinydb.agent_memory_repository import (
    MAX_CONSOLIDATED_CARRIER_RULES,
    TinyDBAgentMemoryRepository,
)
from infrastructure.persistence.tinydb.memory_audit_log_repository import (
    TinyDBMemoryAuditLogRepository,
)


class TestMemoryConsolidationAndRetention:
    """Unit tests for carrier-country consolidation, deduplication, and TTL eviction (T032)."""

    def setup_method(self) -> None:
        """Initialize fresh in-memory repositories and service."""
        self.memory_repo = TinyDBAgentMemoryRepository()
        self.audit_repo = TinyDBMemoryAuditLogRepository()
        self.service = AgentMemoryService(
            memory_repository=self.memory_repo,
            audit_repository=self.audit_repo,
            guardrail_validator=MemoryGuardrailValidator(),
            intent_classifier=UserIntentClassifier(),
        )

    def test_consolidates_multiple_carrier_updates_by_carrier_and_country(self) -> None:
        """Scenario 5: Two distinct updates for SEUR in ES consolidate into 1 profile with 2 active rules, and duplicates merge."""
        now = datetime.now(timezone.utc)
        rec1 = PersistentMemoryRecord(
            memory_id="mem-seur-1",
            category="carrier_rule",
            target_entity="SEUR",
            country_code="ES",
            content="SEUR rural Zaragoza discontinued; local carriers required",
            created_at=now,
            updated_at=now,
        )
        rec2 = PersistentMemoryRecord(
            memory_id="mem-seur-2",
            category="carrier_rule",
            target_entity="SEUR",
            country_code="ES",
            content="Max weight constraint 30kg",
            created_at=now + timedelta(seconds=1),
            updated_at=now + timedelta(seconds=1),
        )
        # Duplicate of rec1 with different memory_id
        rec_dup = PersistentMemoryRecord(
            memory_id="mem-seur-dup",
            category="carrier_rule",
            target_entity="seur",
            country_code="es",
            content="  SEUR rural Zaragoza discontinued; local carriers required  ",
            created_at=now + timedelta(seconds=2),
            updated_at=now + timedelta(seconds=2),
        )

        self.memory_repo.save_memory(rec1)
        self.memory_repo.save_memory(rec2)
        self.memory_repo.save_memory(rec_dup)

        profile = self.service.get_consolidated_carrier_profile("SEUR", "ES")
        assert profile is not None
        assert profile.carrier.upper() == "SEUR"
        assert profile.country_code == "ES"
        assert len(profile.active_rules) == 2
        assert "SEUR rural Zaragoza discontinued; local carriers required" in profile.active_rules
        assert "Max weight constraint 30kg" in profile.active_rules

    def test_enforces_max_20_active_constraints_per_carrier_country_profile(self) -> None:
        """Carrier-country profile must cap active rules at 20, deactivating oldest overflow."""
        base_time = datetime.now(timezone.utc) - timedelta(hours=1)
        for i in range(25):
            ts = base_time + timedelta(minutes=i)
            self.memory_repo.save_memory(
                PersistentMemoryRecord(
                    memory_id=f"mem-fedex-{i}",
                    category="carrier_rule",
                    target_entity="FedEx",
                    country_code="US",
                    content=f"FedEx Los Angeles operational routing constraint #{i}",
                    created_at=ts,
                    updated_at=ts,
                )
            )

        profile = self.service.get_consolidated_carrier_profile("FedEx", "US")
        assert profile is not None
        assert len(profile.active_rules) == MAX_CONSOLIDATED_CARRIER_RULES
        # Oldest 5 (0..4) should have been evicted/deactivated, newest 20 (5..24) retained
        assert "FedEx Los Angeles operational routing constraint #0" not in profile.active_rules
        assert "FedEx Los Angeles operational routing constraint #24" in profile.active_rules

    def test_incident_context_default_14_day_ttl_and_eviction(self) -> None:
        """Incident context memories default to 14-day TTL and are evicted once cutoff passes."""
        proposal, _ = self.service.evaluate_turn_for_proposal(
            user_message="The delays reported across Los Angeles branches this week are due to a port strike, not our fulfillment operations; this is the third ticket on this topic.",
            base_answer="Noted.",
            thread_id="ttl-session-1",
        )
        assert proposal is not None

        res = self.service.resolve_pending_proposal(
            thread_id="ttl-session-1",
            user_message="Yes, remember this incident context.",
        )
        assert res is not None and res["committed_memory_id"] is not None

        stored = self.memory_repo.get_memory(res["committed_memory_id"])
        assert stored is not None
        assert stored.expires_at is not None
        # Verify default TTL is ~14 days from creation
        ttl_days = (stored.expires_at - stored.created_at).days
        assert 13 <= ttl_days <= 15

        # Evict at +15 days in the future
        future_cutoff = datetime.now(timezone.utc) + timedelta(days=15)
        evicted_count = self.service.evict_expired_memories(cutoff_time=future_cutoff)
        assert evicted_count == 1
        assert self.memory_repo.get_memory(res["committed_memory_id"]) is None
