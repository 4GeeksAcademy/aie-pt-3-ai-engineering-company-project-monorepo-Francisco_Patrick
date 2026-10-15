"""User administration application service orchestrating user identity and profiles."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from application.auth.dto import UserCreateDTO
from domain.auth.models import Profile, User
from domain.auth.ports import ProfileRepositoryPort, SecurityPort, UserRepositoryPort
from domain.common.exceptions import DuplicateEntityError


class UserService:
    """Application use case service managing user account lifecycles."""

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        profile_repo: ProfileRepositoryPort,
        security_port: SecurityPort,
    ) -> None:
        """Initialize service with injected repositories and security port."""
        self.user_repo = user_repo
        self.profile_repo = profile_repo
        self.security_port = security_port

    def register_user(self, user_in: Any) -> User:
        """Register a new user account with linked profile, checking for duplicate email."""
        email = user_in.email
        password = user_in.password

        if self.user_repo.get_by_email(email):
            raise DuplicateEntityError(entity_name="User", field="email", value=email)

        user_id = str(uuid.uuid4())
        hashed_password = self.security_port.hash_password(password)
        created_at = datetime.now(timezone.utc).isoformat()

        user = User(
            id=user_id,
            email=email,
            hashed_password=hashed_password,
            role="user",
            is_active=True,
            created_at=created_at,
        )
        self.user_repo.save(user)

        # Linked profile
        profile_obj = getattr(user_in, "profile", None)
        profile = Profile(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=getattr(profile_obj, "name", None) if profile_obj else None,
            phone=getattr(profile_obj, "phone", None) if profile_obj else None,
            address=getattr(profile_obj, "address", None) if profile_obj else None,
            updated_at=created_at,
        )
        self.profile_repo.save(profile)

        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user account by ID."""
        user = self.user_repo.get_by_id(user_id)
        if user and not isinstance(user, User):
            return User(**user)
        return user

    def list_users(self) -> List[User]:
        """List all registered users."""
        users = self.user_repo.list_all()
        return [u if isinstance(u, User) else User(**u) for u in users]

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user properties (role, active status, credentials)."""
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        update_dict = dict(update_data)
        if "password" in update_dict:
            update_dict["hashed_password"] = self.security_port.hash_password(
                update_dict.pop("password")
            )

        if hasattr(self.user_repo, "update"):
            res = self.user_repo.update(user_id, update_dict)
            return User(**res) if res else None

        user_data = user.model_dump()
        user_data.update(update_dict)
        updated_user = User(**user_data)
        return self.user_repo.save(updated_user)

    def delete_user(self, user_id: str) -> bool:
        """Delete user account and cascade delete profile."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        self.profile_repo.delete_by_user_id(user_id)
        return self.user_repo.delete(user_id)


__all__ = ["UserService"]
