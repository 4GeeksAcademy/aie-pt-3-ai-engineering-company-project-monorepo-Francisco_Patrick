from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from application.services.auth_service import AuthService
from domain.exceptions import AuthenticationError, UserInactiveError
from domain.models import User
from presentation.dependencies import get_current_user, get_auth_service_dep

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


class ForgotPasswordRequestModel(BaseModel):
    email: str

@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequestModel,
    auth_service: AuthService = Depends(get_auth_service_dep)
):
    from infrastructure.database import get_db
    from infrastructure.adapters.tiny_db_repository import TinyDBPasswordResetTokenRepository, TinyDBAuditLogRepository
    from infrastructure.middleware.rate_limiter import RateLimiter
    from application.services.email_service import EmailService

    db = get_db()
    token_repo = TinyDBPasswordResetTokenRepository(db)
    audit_repo = TinyDBAuditLogRepository(db)
    email_service = EmailService()
    rate_limiter = RateLimiter()

    return auth_service.request_password_reset(
        email=payload.email,
        token_repo=token_repo,
        audit_repo=audit_repo,
        email_service=email_service,
        rate_limiter=rate_limiter
    )


class ResetPasswordRequestModel(BaseModel):
    token: str
    new_password: str

@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequestModel,
    auth_service: AuthService = Depends(get_auth_service_dep)
):
    from infrastructure.database import get_db
    from infrastructure.adapters.tiny_db_repository import TinyDBPasswordResetTokenRepository, TinyDBAuditLogRepository

    db = get_db()
    token_repo = TinyDBPasswordResetTokenRepository(db)
    audit_repo = TinyDBAuditLogRepository(db)

    try:
        return auth_service.reset_password(
            raw_token=payload.token,
            new_password=payload.new_password,
            token_repo=token_repo,
            audit_repo=audit_repo
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


class ChangePasswordRequestModel(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequestModel,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service_dep)
):
    from infrastructure.database import get_db
    from infrastructure.adapters.tiny_db_repository import TinyDBAuditLogRepository

    db = get_db()
    audit_repo = TinyDBAuditLogRepository(db)

    try:
        return auth_service.change_password(
            user_id=current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            audit_repo=audit_repo
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )



