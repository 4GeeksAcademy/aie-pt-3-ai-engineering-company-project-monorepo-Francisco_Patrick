# Domain Port Contracts: Agent Memory & Self-Improvement

**Feature**: `029-agent-memory-self-improvement`  
**Location**: `services/api/domain/agent/ports.py`  
**Date**: 2026-11-21  

Adheres strictly to Hexagonal Architecture, Monorepo Constitution Principle I (Service Boundaries & Domain Isolation), and Principle VII (Vector Database Isolation).

---

## 1. AgentMemoryRepositoryPort

Strictly isolated from Qdrant static knowledge (`trackflow_knowledge`). Manages persistent storage and retrieval of confirmed operational memories.

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from domain.agent.entities import (
    ConsolidatedCarrierProfile,
    MemoryCategory,
    PersistentMemoryRecord,
)


class AgentMemoryRepositoryPort(ABC):
    """Port interface for storing, querying, and consolidating persistent agent memories."""

    @abstractmethod
    def save_memory(self, record: PersistentMemoryRecord) -> PersistentMemoryRecord:
        """Persist or update an approved operational memory record.
        
        Args:
            record: PersistentMemoryRecord domain object to store.
            
        Returns:
            The stored PersistentMemoryRecord with assigned identifiers.
        """

    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[PersistentMemoryRecord]:
        """Retrieve a persistent memory record by its identifier.
        
        Args:
            memory_id: Unique UUID string.
            
        Returns:
            PersistentMemoryRecord if found and active, otherwise None.
        """

    @abstractmethod
    def search_memories(
        self,
        category: Optional[MemoryCategory] = None,
        target_entity: Optional[str] = None,
        country_code: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PersistentMemoryRecord]:
        """Search active memories by category, target entity, or country.
        
        Args:
            category: Optional functional category filter.
            target_entity: Optional entity filter (carrier, region, client ID).
            country_code: Optional ISO country code filter ("ES", "US").
            active_only: Whether to exclude expired or inactive items.
            
        Returns:
            List of matching PersistentMemoryRecord items.
        """

    @abstractmethod
    def get_consolidated_carrier_profile(
        self,
        carrier: str,
        country_code: str,
    ) -> Optional[ConsolidatedCarrierProfile]:
        """Retrieve the consolidated profile of active operational rules for a carrier and country.
        
        Args:
            carrier: Carrier name (e.g. "SEUR", "FedEx").
            country_code: ISO country code ("ES", "US").
            
        Returns:
            ConsolidatedCarrierProfile if records exist, otherwise None.
        """

    @abstractmethod
    def evict_expired(self, cutoff_time: datetime) -> int:
        """Evict or mark inactive any records whose expires_at is older than cutoff_time.
        
        Args:
            cutoff_time: UTC threshold timestamp.
            
        Returns:
            Count of evicted records.
        """
```

---

## 2. MemoryAuditLogRepositoryPort

Append-only, immutable audit store recording every proposal evaluation, user feedback event, and storage change.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.agent.entities import MemoryAuditLogEntry


class MemoryAuditLogRepositoryPort(ABC):
    """Port interface for persisting and querying immutable memory lifecycle audit logs."""

    @abstractmethod
    def record_entry(self, entry: MemoryAuditLogEntry) -> None:
        """Append an immutable audit entry to the audit log store.
        
        Args:
            entry: MemoryAuditLogEntry domain object.
        """

    @abstractmethod
    def list_entries(
        self,
        proposal_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryAuditLogEntry]:
        """Query audit log entries ordered newest first.
        
        Args:
            proposal_id: Optional filter for a specific proposal lifecycle.
            event_type: Optional filter by event type ("proposed", "approved", "rejected", etc.).
            limit: Maximum records to return.
            
        Returns:
            List of MemoryAuditLogEntry records.
        """
```

---

## 3. MemoryGuardrailPort

Validates candidate memory proposals against TrackFlow operational boundaries and anti-poisoning defenses.

```python
from abc import ABC, abstractmethod
from domain.agent.entities import MemoryGuardrailVerdict


class MemoryGuardrailPort(ABC):
    """Port interface for evaluating candidate memories against enterprise guardrails."""

    @abstractmethod
    def validate_candidate(
        self,
        content: str,
        category: str,
        target_entity: str,
    ) -> MemoryGuardrailVerdict:
        """Validate candidate memory content against forbidden categories.
        
        Checks:
        1. No B2C end-consumer physical addresses or sensitive B2B premises.
        2. No internal warehouse floor layouts, shelf paths, or physical security routes.
        3. No one-off single package complaints without repeatable operational pattern.
        4. No commercial contract negotiation or sales CRM data.
        5. No global policy overrides disguised as carrier notes.
        
        Args:
            content: Candidate summary / text.
            category: Proposed category.
            target_entity: Carrier or entity identifier.
            
        Returns:
            MemoryGuardrailVerdict with allowed=True or allowed=False with violation details.
        """
```

---

## 4. UserIntentClassifierPort

Classifies user conversational turns following a memory proposal into discrete outcomes.

```python
from abc import ABC, abstractmethod
from domain.agent.entities import UserIntentClassification


class UserIntentClassifierPort(ABC):
    """Port interface for classifying user follow-up intent regarding active memory proposals."""

    @abstractmethod
    def classify(
        self,
        user_message: str,
        proposal_summary: str,
    ) -> UserIntentClassification:
        """Classify user response into approve, reject, edit, or unrelated_or_ambiguous.
        
        Args:
            user_message: The follow-up conversational text from the user.
            proposal_summary: The summary of the pending proposal being evaluated.
            
        Returns:
            UserIntentClassification containing intent, confidence, optional refined_rule,
            and optional residual_query.
        """
```
