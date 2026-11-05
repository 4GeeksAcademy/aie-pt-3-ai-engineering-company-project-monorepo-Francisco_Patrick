# Contract: Dead Letter Queue (DLQ) Persistence & Recovery

**Storage**: Relational Database (`inventory.db` / PostgreSQL)  
**Table**: `dead_letter_queue`  
**Purpose**: Quarantines permanently failed Celery tasks after exhausting 3 consecutive retry attempts with full diagnostic audit metadata.  

---

## 1. Storage Interface Port: `DeadLetterQueuePort`

Located in `domain/common/ports.py` (or `services/api/domain/queue/ports.py`):

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

class DeadLetterQueuePort(ABC):
    @abstractmethod
    def record_failure(
        self,
        task_id: str,
        task_name: str,
        attempt_number: int,
        error_message: str,
        payload_reference: Optional[str] = None,
    ) -> int:
        """Persist a failed task execution record to the Dead Letter Queue.
        
        Args:
            task_id: The UUID of the failed Celery task.
            task_name: Fully qualified task identifier.
            attempt_number: Total retry attempts made (normally 3).
            error_message: Sanitized error description.
            payload_reference: Staging path or parameter reference.

        Returns:
            The primary key ID of the persisted record.
        """
        pass

    @abstractmethod
    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        task_name: Optional[str] = None,
    ) -> List[dict]:
        """Query quarantined task failure records for inspection."""
        pass
```

---

## 2. Table Schema Definition

```sql
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(64) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 3,
    error_message TEXT NOT NULL,
    payload_reference TEXT NULL,
    failed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_dlq_task_id ON dead_letter_queue (task_id);
CREATE INDEX IF NOT EXISTS ix_dlq_failed_at ON dead_letter_queue (failed_at);
```

---

## 3. Data Invariants & Privacy Rules

1. **Attempt Threshold**: `attempt_number` MUST be equal to `3` when recording a retried failure (or `1` if an unretryable fatal error occurs).
2. **PII and Secret Sanitization**:
   - Any sensitive tokens (`Bearer ...`, `token=...`, `password=...`, etc.) are stripped or masked as `***REDACTED***`.
   - Email addresses are masked (e.g. `u***@domain.com`).
   - Raw stack traces are truncated to at most 1,000 characters and contain no filesystem paths outside repo bounds.
3. **Acknowledgment Ordering**: Celery worker message is only acknowledged (`ACK`) AFTER the database transaction commits the DLQ record.

