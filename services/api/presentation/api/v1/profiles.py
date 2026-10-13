"""Profiles API router (canonical v1, also mounted at the legacy /profiles prefix)."""

from fastapi import APIRouter, Depends, HTTPException, status

from application.services.profile_service import ProfileService
from domain.models import Profile, ProfileBase, User
from presentation.dependencies import get_current_user, get_profile_service_dep

router = APIRouter(tags=["Profiles"])


@router.get("/me", response_model=Profile)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service_dep),
) -> Profile:
    """Return the authenticated user's profile."""
    profile = profile_service.get_profile_by_user_id(current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.put("/me", response_model=Profile)
def update_my_profile(
    profile_update: ProfileBase,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service_dep),
) -> Profile:
    """Update the authenticated user's profile."""
    try:
        return profile_service.update_profile(current_user.id, profile_update)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
