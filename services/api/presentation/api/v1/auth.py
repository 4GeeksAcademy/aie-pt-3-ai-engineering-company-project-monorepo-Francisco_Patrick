"""Authentication API router (canonical v1, also mounted at the legacy /auth prefix)."""

from typing import TYPE_CHECKING, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from application.services.auth_service import AuthService
from domain.exceptions import AuthenticationError, UserInactiveError
from domain.models import MessageResponse, User, UserResponse
from presentation.dependencies import (
    get_audit_log_repository_dep,
    get_auth_service_dep,
    get_current_user,
    get_email_service_dep,
    get_password_reset_token_repository_dep,
    get_rate_limiter_dep,
)

if TYPE_CHECKING:
    from application.services.email_service import EmailService
    from infrastructure.adapters.tiny_db_repository import (
        TinyDBAuditLogRepository,
        TinyDBPasswordResetTokenRepository,
    )
    from infrastructure.middleware.rate_limiter import RateLimiter

router = APIRouter(tags=["Authentication"])


class Token(BaseModel):
    access_token: str
    token_type: str


class ForgotPasswordRequestModel(BaseModel):
    email: str


class ResetPasswordRequestModel(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequestModel(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service_dep),
) -> Dict[str, str]:
    """Exchange credentials for a bearer access token."""
    try:
        token = auth_service.authenticate_user(
            email=form_data.username, password=form_data.password
        )
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


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's information."""
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequestModel,
    auth_service: AuthService = Depends(get_auth_service_dep),
    token_repo: "TinyDBPasswordResetTokenRepository" = Depends(
        get_password_reset_token_repository_dep
    ),
    audit_repo: "TinyDBAuditLogRepository" = Depends(get_audit_log_repository_dep),
    email_service: "EmailService" = Depends(get_email_service_dep),
    rate_limiter: "RateLimiter" = Depends(get_rate_limiter_dep),
) -> MessageResponse:
    """Request a password reset email (responds identically for unknown emails)."""
    return auth_service.request_password_reset(
        email=payload.email,
        token_repo=token_repo,
        audit_repo=audit_repo,
        email_service=email_service,
        rate_limiter=rate_limiter,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequestModel,
    auth_service: AuthService = Depends(get_auth_service_dep),
    token_repo: "TinyDBPasswordResetTokenRepository" = Depends(
        get_password_reset_token_repository_dep
    ),
    audit_repo: "TinyDBAuditLogRepository" = Depends(get_audit_log_repository_dep),
) -> MessageResponse:
    """Complete a password reset using a previously issued token."""
    try:
        return auth_service.reset_password(
            raw_token=payload.token,
            new_password=payload.new_password,
            token_repo=token_repo,
            audit_repo=audit_repo,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequestModel,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service_dep),
    audit_repo: "TinyDBAuditLogRepository" = Depends(get_audit_log_repository_dep),
) -> MessageResponse:
    """Change the authenticated user's password."""
    try:
        return auth_service.change_password(
            user_id=current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            audit_repo=audit_repo,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
