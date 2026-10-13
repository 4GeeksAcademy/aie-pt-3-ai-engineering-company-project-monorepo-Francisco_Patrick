import uuid
from datetime import datetime, timezone
from typing import Optional, List

from domain.models import UserCreate, User, ProfileBase, Profile
from domain.ports import UserRepositoryPort, ProfileRepositoryPort, SecurityPort
from domain.exceptions import AuthenticationError

class UserService:
    def __init__(
        self,
        user_repo: UserRepositoryPort,
        profile_repo: ProfileRepositoryPort,
        security_port: SecurityPort
    ):
        self.user_repo = user_repo
        self.profile_repo = profile_repo
        self.security_port = security_port

    def register_user(self, user_in: UserCreate) -> User:
        # Check if email exists
        if self.user_repo.get_by_email(user_in.email):
            raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        hashed_password = self.security_port.hash_password(user_in.password)
        created_at = datetime.now(timezone.utc).isoformat()

        user_dict = {
            "id": user_id,
            "email": user_in.email,
            "hashed_password": hashed_password,
            "is_active": True,  # Enforce is_active=True
            "role": "user",     # Enforce default role 'user'
            "created_at": created_at
        }
        
        self.user_repo.create(user_dict)

        # Create linked profile
        profile_id = str(uuid.uuid4())
        profile_dict = {
            "id": profile_id,
            "user_id": user_id,
            "name": user_in.profile.name if user_in.profile else None,
            "phone": user_in.profile.phone if user_in.profile else None,
            "address": user_in.profile.address if user_in.profile else None,
        }
        self.profile_repo.create(profile_dict)

        return User(**user_dict)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        data = self.user_repo.get_by_id(user_id)
        if data:
            return User(**data)
        return None

    def list_users(self) -> List[User]:
        users_data = self.user_repo.get_all()
        return [User(**u) for u in users_data]

    def update_user(self, user_id: str, update_data: dict) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        # If updating password, hash it
        if "password" in update_data:
            update_data["hashed_password"] = self.security_port.hash_password(update_data.pop("password"))

        updated = self.user_repo.update(user_id, update_data)
        return User(**updated) if updated else None

    def delete_user(self, user_id: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
            
        # Delete linked profile first if needed, though TinyDBProfileRepository doesn't enforce foreign keys,
        # it's good practice.
        profile_data = self.profile_repo.get_by_user_id(user_id)
        if profile_data:
            self.profile_repo.delete(profile_data["id"])
            
        return self.user_repo.delete(user_id)
