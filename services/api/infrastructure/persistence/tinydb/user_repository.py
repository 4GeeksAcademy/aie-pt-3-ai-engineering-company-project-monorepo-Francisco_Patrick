"""TinyDB persistence adapter for User domain entities.

Implements UserRepositoryPort using TinyDB document store.
"""

from typing import Any, Dict, List, Optional
from tinydb import Query, TinyDB

from domain.auth.models import User
from domain.auth.ports import UserRepositoryPort
from infrastructure.persistence.tinydb.client import get_table, get_tinydb


class TinyDBUserRepository(UserRepositoryPort):
    """TinyDB document store adapter implementing UserRepositoryPort."""

    def __init__(self, db: Optional[TinyDB] = None, table_name: str = "users") -> None:
        """Initialize user repository with TinyDB table."""
        self._db = db if db is not None else get_tinydb()
        self.table = get_table(table_name, db=self._db)
        self.UserQuery = Query()

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user by UUID string id."""
        doc = self.table.get(self.UserQuery.id == user_id)
        if not doc:
            return None
        return User(**dict(doc))

    def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve user by email."""
        doc = self.table.get(self.UserQuery.email == email)
        if not doc:
            return None
        return User(**dict(doc))

    def save(self, user: User) -> User:
        """Persist or update user domain entity."""
        user_dict = user.model_dump()
        existing = self.table.get(self.UserQuery.id == user.id)
        if existing:
            self.table.update(user_dict, self.UserQuery.id == user.id)
        else:
            self.table.insert(user_dict)
        return user

    def list_all(self) -> List[User]:
        """List all users."""
        docs = self.table.all()
        return [User(**dict(doc)) for doc in docs]

    def delete(self, user_id: str) -> bool:
        """Delete user by id."""
        removed = self.table.remove(self.UserQuery.id == user_id)
        return len(removed) > 0

    # Dict-based convenience methods matching legacy repository interface
    def create(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy helper inserting user dict."""
        self.table.insert(user_data)
        doc = self.table.get(self.UserQuery.id == user_data["id"])
        return dict(doc) if doc else user_data

    def get_all(self) -> List[Dict[str, Any]]:
        """Legacy helper returning dicts."""
        return [dict(doc) for doc in self.table.all()]

    def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy helper updating user dict."""
        self.table.update(update_data, self.UserQuery.id == user_id)
        doc = self.table.get(self.UserQuery.id == user_id)
        return dict(doc) if doc else None


__all__ = ["TinyDBUserRepository"]
