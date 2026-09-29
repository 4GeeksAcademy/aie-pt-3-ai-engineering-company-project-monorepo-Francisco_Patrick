# Interface Contracts: Caching & Optimization

## 1. Backend Cache Manager Protocol (`services/api/infrastructure/cache.py`)

### Interface: `ResponseCache`

```python
from typing import Any, Optional, Callable, TypeVar

T = TypeVar("T")

class ResponseCache:
    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value if present and unexpired."""
        ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store value with specified TTL expiration."""
        ...

    def invalidate(self, key: str) -> None:
        """Remove a single specific key from the cache."""
        ...

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all keys starting with the given prefix string. Returns count of invalidated keys."""
        ...

    def clear(self) -> None:
        """Purge all entries from the cache."""
        ...
```

---

## 2. HTTP Endpoint Cache Header Behavior

Cached endpoints will include HTTP headers or internal headers indicating cache status:
- `X-Cache-Status`: `HIT` | `MISS` (optional operational diagnostic header)
- Standard payload serialization adheres to the existing OpenAPI DTO contracts defined in Feature 013 (`IncidentSummaryResponse`, `Supplier`, `ProductResponse`).

---

## 3. Frontend Dynamic Import Contracts

### Contract: Next.js Dynamic Imports with Fallbacks
```typescript
import dynamic from 'next/dynamic';

export const DynamicOrdersHistoryTable = dynamic(
  () => import('../../../components/inventory/OrdersHistoryTable'),
  {
    loading: () => <TableSkeletonPlaceholder />,
    ssr: false,
  }
);
```
