from typing import Optional, List, Dict, Any
from tinydb import TinyDB, Query

from domain.ports import UserRepositoryPort, ProfileRepositoryPort

class TinyDBUserRepository(UserRepositoryPort):
    def __init__(self, db: TinyDB):
        self.table = db.table("users")
        self.UserQuery = Query()

    def create(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = self.table.insert(user_data)
        # Store the document ID in the record itself if we rely on TinyDB's internal ID
        # Wait, the spec says `id` (UUID), so we assume user_data already has a UUID string 'id'
        # We will search by 'id' field instead of doc_id.
        return self.get_by_id(user_data["id"])

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        result = self.table.get(self.UserQuery.id == user_id)
        return dict(result) if result else None

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        result = self.table.get(self.UserQuery.email == email)
        return dict(result) if result else None

    def get_all(self) -> List[Dict[str, Any]]:
        return [dict(doc) for doc in self.table.all()]

    def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.table.update(update_data, self.UserQuery.id == user_id)
        return self.get_by_id(user_id)

    def delete(self, user_id: str) -> bool:
        doc_ids = self.table.remove(self.UserQuery.id == user_id)
        return len(doc_ids) > 0


class TinyDBProfileRepository(ProfileRepositoryPort):
    def __init__(self, db: TinyDB):
        self.table = db.table("profiles")
        self.ProfileQuery = Query()

    def create(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        self.table.insert(profile_data)
        return self.get_by_user_id(profile_data["user_id"])

    def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        result = self.table.get(self.ProfileQuery.user_id == user_id)
        return dict(result) if result else None

    def update(self, profile_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.table.update(update_data, self.ProfileQuery.id == profile_id)
        # return the updated one
        result = self.table.get(self.ProfileQuery.id == profile_id)
        return dict(result) if result else None

    def delete(self, profile_id: str) -> bool:
        doc_ids = self.table.remove(self.ProfileQuery.id == profile_id)
        return len(doc_ids) > 0
