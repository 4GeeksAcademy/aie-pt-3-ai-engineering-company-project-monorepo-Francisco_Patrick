"""TinyDB persistence adapter for password reset tokens.

Implements PasswordResetTokenRepositoryPort using TinyDB document store.
"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Dict, Optional
import uuid
from tinydb import Query, TinyDB

from domain.auth.ports import PasswordResetTokenRepositoryPort
from infrastructure.persistence.tinydb.client import get_table, get_tinydb


class TinyDBPasswordResetTokenRepository(PasswordResetTokenRepositoryPort):
    """TinyDB document store adapter implementing PasswordResetTokenRepositoryPort."""

    def __init__(self, db: Optional[TinyDB] = None, table_name: str = "password_reset_tokens") -> None:
        """Initialize password reset token repository with TinyDB table."""
        self._db = db if db is not None else get_tinydb()
        self.table = get_table(table_name, db=self._db)
        self.TokenQuery = Query()

    def _hash_token(self, raw_token: str) -> str:
        """Compute SHA-256 hash of raw token string."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def create_token(
        self, user_id: str, raw_token: str, expires_in_minutes: int = 30
    ) -> Dict[str, Any]:
        """Create and store single-use hashed reset token."""
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
            "created_at": now.isoformat(),
        }
        self.table.insert(doc)
        return doc

    def get_valid_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        """Retrieve valid unexpired and unused token record."""
        token_hash = self._hash_token(raw_token)
        result = self.table.get(
            (self.TokenQuery.token_hash == token_hash)
            & (self.TokenQuery.used_at == None)  # noqa: E711
        )
        if not result:
            return None

        expires_at = datetime.fromisoformat(result["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return None
        return dict(result)

    def mark_used(self, token_id: str) -> bool:
        """Mark token record as consumed."""
        now = datetime.now(timezone.utc).isoformat()
        doc_ids = self.table.update({"used_at": now}, self.TokenQuery.id == token_id)
        return len(doc_ids) > 0

    def invalidate_user_tokens(self, user_id: str) -> int:
        """Invalidate all pending tokens for user_id."""
        now = datetime.now(timezone.utc).isoformat()
        doc_ids = self.table.update(
            {"used_at": now},
            (self.TokenQuery.user_id == user_id)
            & (self.TokenQuery.used_at == None),  # noqa: E711
        )
        return len(doc_ids)


__all__ = ["TinyDBPasswordResetTokenRepository"]
