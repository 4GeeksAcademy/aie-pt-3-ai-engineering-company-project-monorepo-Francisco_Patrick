from fastapi import APIRouter, HTTPException, Depends
from domain.models import UserCreate, User
from application.services.user_service import UserService

# A placeholder dependency to get the user service; we will wire this up in main.py
def get_user_service_dep() -> UserService:
    pass

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=User, status_code=201)
def create_user(
    user_in: UserCreate,
    user_service: UserService = Depends(get_user_service_dep)
):
    try:
        user = user_service.register_user(user_in)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

from typing import List
from presentation.dependencies import get_current_admin_user
from domain.models import UserBase

@router.get("", response_model=List[User])
def list_users(
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user)
):
    return user_service.list_users()

@router.get("/{user_id}", response_model=User)
def get_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user)
):
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=User)
def update_user(
    user_id: str,
    update_data: dict, # Using dict to accept any partial update like role or is_active
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user)
):
    user = user_service.update_user(user_id, update_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service_dep),
    admin_user: User = Depends(get_current_admin_user)
):
    success = user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return None
