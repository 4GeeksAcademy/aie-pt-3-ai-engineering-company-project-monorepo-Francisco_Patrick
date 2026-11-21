"""Dedicated TinyDB persistence adapter for TrackFlow Support Agent operational memory (T006).

Implements `AgentMemoryRepositoryPort` in complete storage isolation from Qdrant static
company knowledge collections (`trackflow_knowledge`), satisfying Monorepo Constitution
Principles I & VII and FR-006.
"""

from datetime import datetime, timezone
import os
import threading
from typing import Any, Dict, List, Optional

from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

from domain.agent.entities import (
    ConsolidatedCarrierProfile,
    MemoryCategory,
    PersistentMemoryRecord,
)
from domain.agent.exceptions import MemoryStorageError
from domain.agent.ports import AgentMemoryRepositoryPort

MAX_CONSOLIDATED_CARRIER_RULES = 20


class TinyDBAgentMemoryRepository(AgentMemoryRepositoryPort):
    """Thread-safe TinyDB adapter for storing, searching, and consolidating agent memories."""

    def __init__(
        self,
        db: Optional[TinyDB] = None,
        db_path: Optional[str] = None,
        table_name: str = "agent_memory",
    ) -> None:
        """Initialize the dedicated TinyDB agent memory repository.

        Args:
            db: Optional existing TinyDB instance (e.g. `TinyDB(storage=MemoryStorage)` for tests).
            db_path: Optional explicit file path for dedicated JSON storage.
            table_name: Document table name (defaults to `'agent_memory'`).
        """
        self._lock = threading.RLock()
        if db is not None:
            self._db = db
        elif db_path is not None:
            resolved = os.path.abspath(db_path)
            dirname = os.path.dirname(resolved)
            if dirname and not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
            self._db = TinyDB(resolved)
        else:
            env_path = os.environ.get("AGENT_MEMORY_DB_PATH")
            if env_path:
                resolved = os.path.abspath(env_path)
                dirname = os.path.dirname(resolved)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname, exist_ok=True)
                self._db = TinyDB(resolved)
            else:
                self._db = TinyDB(storage=MemoryStorage)

        self._table = self._db.table(table_name)
        self._query = Query()

    def save_memory(self, record: PersistentMemoryRecord) -> PersistentMemoryRecord:
        """Persist or update an approved operational memory record.

        Deduplicates identical active rules for the same `(category, target_entity, country_code)`
        and enforces the bounded 20-rule cap per carrier-country profile.
        """
        try:
            with self._lock:
                now = datetime.now(timezone.utc)
                target_norm = record.target_entity.strip()
                country_norm = (
                    record.country_code.strip().upper()
                    if record.country_code and record.country_code.strip()
                    else None
                )
                content_norm = " ".join(record.content.strip().split())

                # Check if memory_id already exists
                existing_by_id = self._table.search(
                    self._query.memory_id == record.memory_id
                )
                if existing_by_id:
                    updated_record = PersistentMemoryRecord(
                        memory_id=record.memory_id,
                        category=record.category,
                        target_entity=target_norm,
                        country_code=country_norm,
                        content=content_norm,
                        source_proposal_id=record.source_proposal_id,
                        operator_confirmed_by=record.operator_confirmed_by,
                        is_active=record.is_active,
                        created_at=record.created_at,
                        updated_at=now,
                        expires_at=record.expires_at,
                    )
                    self._table.update(
                        updated_record.to_dict(),
                        self._query.memory_id == record.memory_id,
                    )
                    return updated_record

                # Check for duplicate active content on the same (category, target_entity, country_code)
                all_docs = self._table.all()
                for doc in all_docs:
                    if not doc.get("is_active", True):
                        continue
                    if doc.get("category") != record.category:
                        continue
                    if (
                        str(doc.get("target_entity") or "").strip().lower()
                        != target_norm.lower()
                    ):
                        continue
                    doc_country = (
                        str(doc.get("country_code")).strip().upper()
                        if doc.get("country_code")
                        else None
                    )
                    if doc_country != country_norm:
                        continue
                    doc_content = " ".join(str(doc.get("content") or "").strip().split())
                    if doc_content.lower() == content_norm.lower():
                        existing_rec = PersistentMemoryRecord.from_dict(dict(doc))
                        merged_rec = PersistentMemoryRecord(
                            memory_id=existing_rec.memory_id,
                            category=existing_rec.category,
                            target_entity=existing_rec.target_entity,
                            country_code=existing_rec.country_code,
                            content=content_norm,
                            source_proposal_id=record.source_proposal_id
                            or existing_rec.source_proposal_id,
                            operator_confirmed_by=record.operator_confirmed_by
                            or existing_rec.operator_confirmed_by,
                            is_active=True,
                            created_at=existing_rec.created_at,
                            updated_at=now,
                            expires_at=record.expires_at or existing_rec.expires_at,
                        )
                        self._table.update(
                            merged_rec.to_dict(),
                            self._query.memory_id == existing_rec.memory_id,
                        )
                        return merged_rec

                normalized_record = PersistentMemoryRecord(
                    memory_id=record.memory_id,
                    category=record.category,
                    target_entity=target_norm,
                    country_code=country_norm,
                    content=content_norm,
                    source_proposal_id=record.source_proposal_id,
                    operator_confirmed_by=record.operator_confirmed_by,
                    is_active=record.is_active,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    expires_at=record.expires_at,
                )
                self._table.insert(normalized_record.to_dict())

                # Enforce bounded growth cap (max 20 active constraints per carrier + country)
                if record.category == "carrier_rule":
                    self._enforce_carrier_profile_bound(target_norm, country_norm)

                return normalized_record
        except Exception as exc:
            raise MemoryStorageError(
                f"Failed to save persistent memory record: {exc}"
            ) from exc

    def _enforce_carrier_profile_bound(
        self, carrier: str, country_code: Optional[str]
    ) -> None:
        """Keep at most MAX_CONSOLIDATED_CARRIER_RULES active records for a carrier + country, deactivating oldest overflow."""
        matching = self.search_memories(
            category="carrier_rule",
            target_entity=carrier,
            country_code=country_code,
            active_only=True,
        )
        if len(matching) <= MAX_CONSOLIDATED_CARRIER_RULES:
            return
        # Sort by updated_at ascending (oldest first)
        sorted_records = sorted(matching, key=lambda r: r.updated_at)
        overflow = sorted_records[: len(matching) - MAX_CONSOLIDATED_CARRIER_RULES]
        for old_rec in overflow:
            self._table.update(
                {"is_active": False},
                self._query.memory_id == old_rec.memory_id,
            )

    def get_memory(self, memory_id: str) -> Optional[PersistentMemoryRecord]:
        """Retrieve a persistent memory record by its identifier."""
        try:
            with self._lock:
                docs = self._table.search(self._query.memory_id == memory_id)
                if not docs:
                    return None
                rec = PersistentMemoryRecord.from_dict(dict(docs[0]))
                if not rec.is_active:
                    return None
                if rec.expires_at and rec.expires_at <= datetime.now(timezone.utc):
                    return None
                return rec
        except Exception as exc:
            raise MemoryStorageError(
                f"Failed to retrieve memory '{memory_id}': {exc}"
            ) from exc

    def search_memories(
        self,
        category: Optional[MemoryCategory] = None,
        target_entity: Optional[str] = None,
        country_code: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PersistentMemoryRecord]:
        """Search active memories by category, target entity, or country."""
        try:
            with self._lock:
                now = datetime.now(timezone.utc)
                all_docs = self._table.all()
                results: List[PersistentMemoryRecord] = []

                target_norm = (
                    target_entity.strip().lower()
                    if target_entity and target_entity.strip()
                    else None
                )
                country_norm = (
                    country_code.strip().upper()
                    if country_code and country_code.strip()
                    else None
                )

                for doc in all_docs:
                    rec = PersistentMemoryRecord.from_dict(dict(doc))
                    if active_only:
                        if not rec.is_active:
                            continue
                        if rec.expires_at is not None and rec.expires_at <= now:
                            continue

                    if category is not None and rec.category != category:
                        continue

                    if target_norm is not None:
                        rec_target = rec.target_entity.strip().lower()
                        if target_norm != rec_target and target_norm not in rec_target:
                            continue

                    if country_norm is not None:
                        rec_country = (
                            rec.country_code.strip().upper()
                            if rec.country_code
                            else None
                        )
                        if rec_country != country_norm:
                            continue

                    results.append(rec)

                results.sort(key=lambda r: r.updated_at)
                return results
        except Exception as exc:
            raise MemoryStorageError(
                f"Failed to search persistent memories: {exc}"
            ) from exc

    def get_consolidated_carrier_profile(
        self,
        carrier: str,
        country_code: str,
    ) -> Optional[ConsolidatedCarrierProfile]:
        """Retrieve the consolidated profile of active operational rules for a carrier and country."""
        carrier_clean = carrier.strip()
        country_clean = country_code.strip().upper() if country_code else "ES"
        records = self.search_memories(
            category="carrier_rule",
            target_entity=carrier_clean,
            country_code=country_clean,
            active_only=True,
        )
        # Filter to exact carrier match case-insensitively
        exact_records = [
            r
            for r in records
            if r.target_entity.strip().lower() == carrier_clean.lower()
        ]
        if not exact_records:
            return None

        active_rules: List[str] = []
        memory_ids: List[str] = []
        seen_lower: set[str] = set()
        latest_ts = exact_records[0].updated_at

        for rec in exact_records:
            rule_text = rec.content.strip()[:250]
            if rule_text.lower() not in seen_lower:
                seen_lower.add(rule_text.lower())
                active_rules.append(rule_text)
                memory_ids.append(rec.memory_id)
            if rec.updated_at > latest_ts:
                latest_ts = rec.updated_at

        # Cap at 20 active constraints per profile
        if len(active_rules) > MAX_CONSOLIDATED_CARRIER_RULES:
            active_rules = active_rules[-MAX_CONSOLIDATED_CARRIER_RULES:]
            memory_ids = memory_ids[-MAX_CONSOLIDATED_CARRIER_RULES:]

        canonical_carrier = exact_records[-1].target_entity
        return ConsolidatedCarrierProfile(
            carrier=canonical_carrier,
            country_code=country_clean,
            active_rules=active_rules,
            memory_ids=memory_ids,
            last_verified_at=latest_ts,
        )

    def evict_expired(self, cutoff_time: datetime) -> int:
        """Evict or mark inactive any records whose expires_at is older than or equal to cutoff_time."""
        try:
            with self._lock:
                cutoff_utc = (
                    cutoff_time
                    if cutoff_time.tzinfo is not None
                    else cutoff_time.replace(tzinfo=timezone.utc)
                )
                evicted_count = 0
                for doc in self._table.all():
                    rec = PersistentMemoryRecord.from_dict(dict(doc))
                    if not rec.is_active:
                        continue
                    if rec.expires_at is not None and rec.expires_at <= cutoff_utc:
                        self._table.update(
                            {"is_active": False, "updated_at": cutoff_utc.isoformat()},
                            self._query.memory_id == rec.memory_id,
                        )
                        evicted_count += 1
                return evicted_count
        except Exception as exc:
            raise MemoryStorageError(
                f"Failed to evict expired memories: {exc}"
            ) from exc

    def count_active(self) -> int:
        """Return total number of active, non-expired persistent memory records."""
        return len(self.search_memories(active_only=True))

    def clear(self) -> None:
        """Remove all records from the table (for test isolation)."""
        with self._lock:
            self._table.truncate()


__all__ = ["MAX_CONSOLIDATED_CARRIER_RULES", "TinyDBAgentMemoryRepository"]
