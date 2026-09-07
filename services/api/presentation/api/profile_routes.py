from fastapi import APIRouter, Depends, HTTPException, status
from domain.models import User, Profile, ProfileBase
from application.services.profile_service import ProfileService
from presentation.dependencies import get_current_user, get_profile_service_dep

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("/me", response_model=Profile)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service_dep)
):
    profile = profile_service.get_profile_by_user_id(current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile

@router.put("/me", response_model=Profile)
def update_my_profile(
    profile_update: ProfileBase,
    current_user: User = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service_dep)
):
    try:
        updated_profile = profile_service.update_profile(current_user.id, profile_update)
        return updated_profile
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
