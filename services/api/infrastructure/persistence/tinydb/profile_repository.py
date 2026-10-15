"""TinyDB persistence adapter for User Profile entities.

Implements ProfileRepositoryPort using TinyDB document store.
"""

from typing import Any, Dict, Optional
import uuid
from tinydb import Query, TinyDB

from domain.auth.models import Profile
from domain.auth.ports import ProfileRepositoryPort
from infrastructure.persistence.tinydb.client import get_table, get_tinydb


class TinyDBProfileRepository(ProfileRepositoryPort):
    """TinyDB document store adapter implementing ProfileRepositoryPort."""

    def __init__(self, db: Optional[TinyDB] = None, table_name: str = "profiles") -> None:
        """Initialize profile repository with TinyDB table."""
        self._db = db if db is not None else get_tinydb()
        self.table = get_table(table_name, db=self._db)
        self.ProfileQuery = Query()

    def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        """Retrieve profile associated with user_id."""
        doc = self.table.get(self.ProfileQuery.user_id == user_id)
        if not doc:
            return None
        return Profile(**dict(doc))

    def save(self, profile: Profile) -> Profile:
        """Persist or update profile entity."""
        data = profile.model_dump()
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
            profile.id = data["id"]

        existing = self.table.get(self.ProfileQuery.user_id == profile.user_id)
        if existing:
            self.table.update(data, self.ProfileQuery.user_id == profile.user_id)
        else:
            self.table.insert(data)
        return profile

    def delete_by_user_id(self, user_id: str) -> bool:
        """Delete profile for user_id."""
        removed = self.table.remove(self.ProfileQuery.user_id == user_id)
        return len(removed) > 0

    # Dict-based convenience methods matching legacy repository interface
    def create(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy helper inserting profile dict."""
        self.table.insert(profile_data)
        doc = self.table.get(self.ProfileQuery.user_id == profile_data["user_id"])
        return dict(doc) if doc else profile_data

    def update(self, profile_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy helper updating profile dict by profile id."""
        self.table.update(update_data, self.ProfileQuery.id == profile_id)
        doc = self.table.get(self.ProfileQuery.id == profile_id)
        return dict(doc) if doc else None

    def delete(self, profile_id: str) -> bool:
        """Legacy helper deleting by profile id."""
        removed = self.table.remove(self.ProfileQuery.id == profile_id)
        return len(removed) > 0


__all__ = ["TinyDBProfileRepository"]
