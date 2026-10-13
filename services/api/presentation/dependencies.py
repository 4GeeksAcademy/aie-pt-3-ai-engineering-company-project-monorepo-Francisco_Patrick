"""FastAPI dependency injection providers.

Centralizes dependency resolution across presentation endpoints, providing access
to database connections, driven adapters, repository ports, and application services.
"""

from typing import TYPE_CHECKING, Any, Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session
from tinydb import TinyDB

from domain.models import User
from domain.exceptions import AuthenticationError
from domain.ports import (
    ProfileRepositoryPort,
    SecurityPort,
    UserRepositoryPort,
)
from domain.common.ports import CachePort
from domain.inventory.ports import InventoryRepositoryPort
from domain.suppliers.ports import SupplierRepositoryPort
from application.services.auth_service import AuthService
from application.services.incident_service import IncidentService
from application.services.profile_service import ProfileService
from application.services.user_service import UserService
from application.suppliers.supplier_service import SupplierService
from application.inventory.inventory_service import InventoryService
from application.telemetry.telemetry_service import TelemetryService
from application.incidents.csv_report_service import IncidentCsvReportService

if TYPE_CHECKING:
    from application.services.email_service import EmailService
    from infrastructure.adapters.tiny_db_repository import (
        TinyDBAuditLogRepository,
        TinyDBPasswordResetTokenRepository,
    )
    from infrastructure.middleware.rate_limiter import RateLimiter


# --- OAuth2 Scheme ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# --- Persistence Dependencies ---
def get_tinydb_dep() -> TinyDB:
    """Dependency provider for TinyDB document store client."""
    from infrastructure.persistence.tinydb.client import get_tinydb
    return get_tinydb()


def get_sqlmodel_session_dep() -> Generator[Session, None, None]:
    """Dependency provider for SQLModel relational database session."""
    from infrastructure.persistence.sqlmodel.client import get_db
    yield from get_db()


# --- Infrastructure Adapter Dependencies ---
def get_security_adapter_dep() -> SecurityPort:
    """Dependency provider for cryptographic and JWT token security port."""
    from infrastructure.adapters.security_adapter import JwtSecurityAdapter
    return JwtSecurityAdapter()


def get_cache_dep() -> CachePort:
    """Dependency provider for in-memory CachePort adapter."""
    from infrastructure.cache.memory_cache_adapter import memory_cache_adapter
    return memory_cache_adapter


# --- Repository Port Dependencies ---
def get_user_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> UserRepositoryPort:
    """Dependency provider for TinyDBUserRepository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBUserRepository
    return TinyDBUserRepository(db)


def get_profile_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> ProfileRepositoryPort:
    """Dependency provider for TinyDBProfileRepository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBProfileRepository
    return TinyDBProfileRepository(db)


def get_incident_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> Any:
    """Dependency provider for TinyDBIncidentRepository."""
    from infrastructure.adapters.tiny_db_incident_repository import TinyDBIncidentRepository
    return TinyDBIncidentRepository(db)


# --- Application Service Dependencies ---
def get_user_service_dep(
    user_repo: UserRepositoryPort = Depends(get_user_repository_dep),
    profile_repo: ProfileRepositoryPort = Depends(get_profile_repository_dep),
    security_port: SecurityPort = Depends(get_security_adapter_dep),
) -> UserService:
    """Dependency provider for UserService."""
    return UserService(
        user_repo=user_repo,
        profile_repo=profile_repo,
        security_port=security_port,
    )


def get_auth_service_dep(
    user_repo: UserRepositoryPort = Depends(get_user_repository_dep),
    security_port: SecurityPort = Depends(get_security_adapter_dep),
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(
        user_repo=user_repo,
        security_port=security_port,
    )


def get_profile_service_dep(
    profile_repo: ProfileRepositoryPort = Depends(get_profile_repository_dep),
) -> ProfileService:
    """Dependency provider for ProfileService."""
    return ProfileService(profile_repo=profile_repo)


def get_incident_service_dep(
    incident_repo: Any = Depends(get_incident_repository_dep),
) -> IncidentService:
    """Dependency provider for IncidentService."""
    return IncidentService(repo=incident_repo)


def get_supplier_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> SupplierRepositoryPort:
    """Dependency provider for TinyDBSupplierRepository."""
    from infrastructure.persistence.tinydb.supplier_repository import TinyDBSupplierRepository
    return TinyDBSupplierRepository(db)


def get_supplier_service_dep(
    supplier_repo: SupplierRepositoryPort = Depends(get_supplier_repository_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> SupplierService:
    """Dependency provider for SupplierService."""
    return SupplierService(supplier_repo=supplier_repo, cache=cache)


def get_inventory_repository_dep(
    session: Session = Depends(get_sqlmodel_session_dep),
) -> InventoryRepositoryPort:
    """Dependency provider for SQLModelInventoryRepository bound to the request session."""
    from infrastructure.persistence.sqlmodel.inventory_repository import SQLModelInventoryRepository
    return SQLModelInventoryRepository(session)


def get_inventory_service_dep(
    inventory_repo: InventoryRepositoryPort = Depends(get_inventory_repository_dep),
    cache: CachePort = Depends(get_cache_dep),
) -> InventoryService:
    """Dependency provider for InventoryService."""
    return InventoryService(inventory_repo=inventory_repo, cache=cache)


def get_telemetry_service_dep() -> TelemetryService:
    """Dependency provider for TelemetryService with the default logging sink."""
    return TelemetryService()


def get_incident_csv_report_service_dep(
    cache: CachePort = Depends(get_cache_dep),
) -> IncidentCsvReportService:
    """Dependency provider for IncidentCsvReportService wired with the shared CSV analyzer."""
    from shared.analyzer.engine import analyze_csv_stream
    return IncidentCsvReportService(cache=cache, analyzer=analyze_csv_stream)


# --- Password Reset Collaborators ---
def get_password_reset_token_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> "TinyDBPasswordResetTokenRepository":
    """Dependency provider for the password reset token repository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBPasswordResetTokenRepository
    return TinyDBPasswordResetTokenRepository(db)


def get_audit_log_repository_dep(
    db: TinyDB = Depends(get_tinydb_dep),
) -> "TinyDBAuditLogRepository":
    """Dependency provider for the security audit log repository."""
    from infrastructure.adapters.tiny_db_repository import TinyDBAuditLogRepository
    return TinyDBAuditLogRepository(db)


def get_email_service_dep() -> "EmailService":
    """Dependency provider for the transactional email service."""
    from application.services.email_service import EmailService
    return EmailService()


def get_rate_limiter_dep() -> "RateLimiter":
    """Dependency provider for the password reset rate limiter (fresh instance per request)."""
    from infrastructure.middleware.rate_limiter import RateLimiter
    return RateLimiter()


# --- Authentication & Authorization Guards ---
def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service_dep),
    security_adapter: SecurityPort = Depends(get_security_adapter_dep),
) -> User:
    """Extract and validate the currently authenticated user from Bearer JWT."""
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
    """Enforce administrator role permissions for guarded endpoints."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin role required.",
        )
    return current_user


__all__ = [
    "get_audit_log_repository_dep",
    "get_auth_service_dep",
    "get_cache_dep",
    "get_current_admin_user",
    "get_current_user",
    "get_email_service_dep",
    "get_incident_csv_report_service_dep",
    "get_incident_repository_dep",
    "get_incident_service_dep",
    "get_inventory_repository_dep",
    "get_inventory_service_dep",
    "get_password_reset_token_repository_dep",
    "get_profile_repository_dep",
    "get_profile_service_dep",
    "get_rate_limiter_dep",
    "get_security_adapter_dep",
    "get_sqlmodel_session_dep",
    "get_supplier_repository_dep",
    "get_supplier_service_dep",
    "get_telemetry_service_dep",
    "get_tinydb_dep",
    "get_user_repository_dep",
    "get_user_service_dep",
    "oauth2_scheme",
]
