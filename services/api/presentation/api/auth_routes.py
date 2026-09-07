from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from application.services.auth_service import AuthService
from domain.exceptions import AuthenticationError, UserInactiveError
from domain.models import User
from presentation.dependencies import get_current_user

# A placeholder dependency to get the auth service; we will wire this up in main.py
def get_auth_service_dep() -> AuthService:
    pass

router = APIRouter(prefix="/auth", tags=["Authentication"])

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service_dep)
):
    try:
        token = auth_service.authenticate_user(email=form_data.username, password=form_data.password)
        return {"access_token": token, "token_type": "bearer"}
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=User)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated user's information.
    """
    return current_user
