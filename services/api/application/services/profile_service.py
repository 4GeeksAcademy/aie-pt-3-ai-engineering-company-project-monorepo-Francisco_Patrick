from typing import Optional

from domain.models import Profile, ProfileBase
from domain.ports import ProfileRepositoryPort

class ProfileService:
    def __init__(self, profile_repo: ProfileRepositoryPort):
        self.profile_repo = profile_repo

    def get_profile_by_user_id(self, user_id: str) -> Optional[Profile]:
        data = self.profile_repo.get_by_user_id(user_id)
        if data:
            return Profile(**data)
        return None

    def update_profile(self, user_id: str, profile_update: ProfileBase) -> Profile:
        existing = self.profile_repo.get_by_user_id(user_id)
        if not existing:
            raise ValueError("Profile not found for user")
            
        updated_data = self.profile_repo.update(
            existing["id"],
            profile_update.model_dump(exclude_unset=True)
        )
        return Profile(**updated_data)
