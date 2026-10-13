# Driven Port Interface Specifications

**Service**: `services/api`  
**Purpose**: Formal abstract interfaces (Python `abc.ABC`) defining all boundary contracts between the application layer and driven infrastructure adapters.

---

## 1. Supplier Repository Port (`domain/suppliers/ports.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.suppliers.models import Supplier

class SupplierRepositoryPort(ABC):
    @abstractmethod
    def create(self, supplier: Supplier) -> Supplier:
        """Persists a new supplier entity and returns the saved instance with ID."""
        ...

    @abstractmethod
    def get_by_id(self, supplier_id: int) -> Optional[Supplier]:
        """Retrieves a supplier by its identifier. Returns None if missing."""
        ...

    @abstractmethod
    def list_all(self, country: Optional[str] = None, category: Optional[str] = None) -> List[Supplier]:
        """Lists suppliers matching optional country and category filters."""
        ...

    @abstractmethod
    def update_rate(self, supplier_id: int, cost_per_kg: float) -> Optional[Supplier]:
        """Updates shipping cost per kg for a supplier."""
        ...

    @abstractmethod
    def update_status(self, supplier_id: int, status: str) -> Optional[Supplier]:
        """Updates operational status ('active' or 'suspended') for a supplier."""
        ...

    @abstractmethod
    def delete(self, supplier_id: int) -> bool:
        """Deletes a supplier record. Returns True if deleted, False if not found."""
        ...
```

---

## 2. Inventory Repository Port (`domain/inventory/ports.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from domain.inventory.models import SKU, StockEntry, StockExit, InventoryProduct

class InventoryRepositoryPort(ABC):
    @abstractmethod
    def create_sku(self, sku: SKU) -> SKU:
        """Creates a new SKU in the catalog."""
        ...

    @abstractmethod
    def get_sku_by_id(self, sku_id: int) -> Optional[SKU]:
        """Retrieves an SKU by internal primary key."""
        ...

    @abstractmethod
    def get_sku_by_code(self, sku_code: str) -> Optional[SKU]:
        """Retrieves an SKU by unique alphanumeric code."""
        ...

    @abstractmethod
    def list_all_products(self) -> List[InventoryProduct]:
        """Retrieves all products with dynamically calculated current stock levels."""
        ...

    @abstractmethod
    def get_product_by_id(self, sku_id: int) -> Optional[InventoryProduct]:
        """Retrieves a single product with calculated current stock level."""
        ...

    @abstractmethod
    def calculate_stock(self, sku_id: int, warehouse_id: str) -> int:
        """Calculates current net stock (Inbound minus Outbound) for SKU in warehouse."""
        ...

    @abstractmethod
    def add_inbound_entry(self, entry: StockEntry) -> StockEntry:
        """Appends an inbound stock arrival transaction."""
        ...

    @abstractmethod
    def add_outbound_exit(self, exit_rec: StockExit) -> StockExit:
        """Appends an outbound stock dispatch transaction."""
        ...

    @abstractmethod
    def list_orders(self) -> List[Dict[str, Any]]:
        """Lists chronological order history joined with SKU data."""
        ...
```

---

## 3. Incident Repository Port (`domain/incidents/ports.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from domain.incidents.models import Incident

class IncidentRepositoryPort(ABC):
    @abstractmethod
    def save(self, incident: Incident) -> Incident:
        """Persists a new or updated incident entity."""
        ...

    @abstractmethod
    def find_by_id(self, incident_id: str) -> Optional[Incident]:
        """Finds an incident by its ID."""
        ...

    @abstractmethod
    def find_all(
        self,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        branch: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Incident]:
        """Filters incidents matching provided query criteria."""
        ...

    @abstractmethod
    def count_summary(self) -> Dict[str, Any]:
        """Calculates 4-dimensional aggregated metric summary totals."""
        ...
```

---

## 4. Auth & User Repository Ports (`domain/auth/ports.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.auth.models import User, Profile, PasswordResetToken, AuditLog

class UserRepositoryPort(ABC):
    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]: ...
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...
    @abstractmethod
    def save(self, user: User) -> User: ...
    @abstractmethod
    def list_all(self) -> List[User]: ...
    @abstractmethod
    def delete(self, user_id: str) -> bool: ...

class ProfileRepositoryPort(ABC):
    @abstractmethod
    def get_by_user_id(self, user_id: str) -> Optional[Profile]: ...
    @abstractmethod
    def save(self, profile: Profile) -> Profile: ...
    @abstractmethod
    def delete_by_user_id(self, user_id: str) -> bool: ...

class SecurityPort(ABC):
    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool: ...
    @abstractmethod
    def get_password_hash(self, password: str) -> str: ...
    @abstractmethod
    def create_access_token(self, data: dict, expires_delta: Optional[int] = None) -> str: ...
    @abstractmethod
    def decode_access_token(self, token: str) -> dict: ...
```

---

## 5. Cache & Notification Ports (`domain/common/ports.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional, Any

class CachePort(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[Any]: ...
    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None: ...
    @abstractmethod
    def invalidate_prefix(self, prefix: str) -> int: ...

class NotificationPort(ABC):
    @abstractmethod
    def send_password_reset(self, to_email: str, reset_link: str) -> bool: ...
```
