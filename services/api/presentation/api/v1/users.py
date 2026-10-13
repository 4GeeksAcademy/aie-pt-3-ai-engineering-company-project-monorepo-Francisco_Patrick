"""Users API router (canonical v1, also mounted at the legacy /users prefix)."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from application.services.user_service import UserService
from domain.models import User, UserCreate, UserResponse
from presentation.dependencies import get_current_admin_user, get_user_service_dep

router = APIRouter(tags=["Users"])


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    user_in: UserCreate,
    user_service: UserService = Depends(get_user_service_dep),
) -> User:
    """Register a new user."""
    try:
        return user_service.register_user(user_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[UserResponse])
def list_users(
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user),
) -> List[User]:
    """List all users (admin only)."""
    return user_service.list_users()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user),
) -> User:
    """Return a user by ID (admin only)."""
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    update_data: Dict[str, Any],  # Accepts any partial update such as role or is_active
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user),
) -> User:
    """Partially update a user (admin only)."""
    try:
        user = user_service.update_user(user_id, update_data)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user),
) -> None:
    """Delete a user (admin only)."""
    success = user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return None
