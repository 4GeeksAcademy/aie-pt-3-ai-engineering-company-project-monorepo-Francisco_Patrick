"""User profile application service orchestrating profile retrieval and mutations."""

from datetime import datetime, timezone
from typing import Any, Optional

from domain.auth.models import Profile
from domain.auth.ports import ProfileRepositoryPort
from domain.common.exceptions import EntityNotFoundError


class ProfileService:
    """Application use case service managing user profile modifications."""

    def __init__(self, profile_repo: ProfileRepositoryPort) -> None:
        """Initialize service with injected profile repository port."""
        self.profile_repo = profile_repo

    def get_profile_by_user_id(self, user_id: str) -> Optional[Profile]:
        """Retrieve profile associated with user_id."""
        profile = self.profile_repo.get_by_user_id(user_id)
        if profile and not isinstance(profile, Profile):
            return Profile(**profile)
        return profile

    def update_profile(self, user_id: str, profile_update: Any) -> Profile:
        """Update profile details for specified user."""
        existing = self.profile_repo.get_by_user_id(user_id)
        if not existing:
            raise EntityNotFoundError(entity_name="Profile", entity_id=user_id)

        existing_profile = (
            existing if isinstance(existing, Profile) else Profile(**existing)
        )
        update_dict = (
            profile_update.model_dump(exclude_unset=True)
            if hasattr(profile_update, "model_dump")
            else dict(profile_update)
        )

        data = existing_profile.model_dump()
        data.update(update_dict)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated_profile = Profile(**data)
        return self.profile_repo.save(updated_profile)


__all__ = ["ProfileService"]
