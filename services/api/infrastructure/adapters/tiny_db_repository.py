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


import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from domain.ports import PasswordResetTokenRepositoryPort, AuditLogRepositoryPort

class TinyDBPasswordResetTokenRepository(PasswordResetTokenRepositoryPort):
    def __init__(self, db: TinyDB):
        self.table = db.table("password_reset_tokens")
        self.TokenQuery = Query()

    def _hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    def create_token(self, user_id: str, raw_token: str, expires_in_minutes: int = 30) -> Dict[str, Any]:
        self.invalidate_user_tokens(user_id)
        token_hash = self._hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=expires_in_minutes)
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
            "used_at": None,
            "created_at": now.isoformat()
        }
        self.table.insert(doc)
        return doc

    def get_valid_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        token_hash = self._hash_token(raw_token)
        result = self.table.get((self.TokenQuery.token_hash == token_hash) & (self.TokenQuery.used_at == None))
        if not result:
            return None
        
        expires_at = datetime.fromisoformat(result["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return None
        return dict(result)

    def mark_used(self, token_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        doc_ids = self.table.update({"used_at": now}, self.TokenQuery.id == token_id)
        return len(doc_ids) > 0

    def invalidate_user_tokens(self, user_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        doc_ids = self.table.update({"used_at": now}, (self.TokenQuery.user_id == user_id) & (self.TokenQuery.used_at == None))
        return len(doc_ids)


class TinyDBAuditLogRepository(AuditLogRepositoryPort):
    def __init__(self, db: TinyDB):
        self.table = db.table("audit_logs")

    def log_event(self, event_type: str, user_id: Optional[str], ip_address: str, details: Optional[str] = None) -> Dict[str, Any]:
        doc = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.table.insert(doc)
        return doc

