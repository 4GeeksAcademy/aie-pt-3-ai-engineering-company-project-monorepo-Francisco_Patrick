from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional

from domain.models import User
from domain.exceptions import AuthenticationError
from domain.ports import SecurityPort
from application.services.user_service import UserService
def get_user_service_dep() -> UserService:
    pass

def get_auth_service_dep():
    pass

def get_profile_service_dep():
    pass

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_security_adapter_dep() -> SecurityPort:
    pass

def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service_dep),
    security_adapter: SecurityPort = Depends(get_security_adapter_dep)
) -> User:
    try:
        user_id = security_adapter.decode_access_token(token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
        
    return user

def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin role required.",
        )
    return current_user

