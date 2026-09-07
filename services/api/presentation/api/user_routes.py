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
