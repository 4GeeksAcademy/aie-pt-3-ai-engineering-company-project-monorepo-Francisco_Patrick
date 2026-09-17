import os
import sys
import pytest

# Ensure JWT_SECRET_KEY is set before importing app or adapters
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-testing-32-bytes!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

# Add services/api directory to sys.path so imports work seamlessly
API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from tinydb import TinyDB
from tinydb.storages import MemoryStorage
from fastapi.testclient import TestClient

from main import app
from infrastructure.adapters.security_adapter import JwtSecurityAdapter
from infrastructure.adapters.tiny_db_repository import (
    TinyDBUserRepository,
    TinyDBProfileRepository,
    TinyDBPasswordResetTokenRepository,
    TinyDBAuditLogRepository
)
from application.services.user_service import UserService
from application.services.auth_service import AuthService
from application.services.profile_service import ProfileService
from presentation.dependencies import (
    get_security_adapter_dep,
    get_user_service_dep,
    get_auth_service_dep,
    get_profile_service_dep
)


@pytest.fixture(autouse=True)
def override_get_db(memory_db, monkeypatch):
    """Overrides infrastructure.database.get_db unless TINYDB_PATH is explicitly set."""
    import infrastructure.database
    original_get_db = infrastructure.database.get_db

    def smart_get_db():
        if "TINYDB_PATH" in os.environ:
            return original_get_db()
        return memory_db

    monkeypatch.setattr(infrastructure.database, "get_db", smart_get_db)


@pytest.fixture
def memory_db():
    """Provides an isolated in-memory TinyDB instance for testing."""
    return TinyDB(storage=MemoryStorage)


@pytest.fixture
def security_adapter():
    """Provides JwtSecurityAdapter instance configured with test secret key."""
    return JwtSecurityAdapter()


@pytest.fixture
def user_repo(memory_db):
    """Provides TinyDBUserRepository backed by in-memory DB."""
    return TinyDBUserRepository(memory_db)


@pytest.fixture
def profile_repo(memory_db):
    """Provides TinyDBProfileRepository backed by in-memory DB."""
    return TinyDBProfileRepository(memory_db)


@pytest.fixture
def token_repo(memory_db):
    """Provides TinyDBPasswordResetTokenRepository backed by in-memory DB."""
    return TinyDBPasswordResetTokenRepository(memory_db)


@pytest.fixture
def audit_repo(memory_db):
    """Provides TinyDBAuditLogRepository backed by in-memory DB."""
    return TinyDBAuditLogRepository(memory_db)


@pytest.fixture
def user_service(user_repo, profile_repo, security_adapter):
    """Provides UserService initialized with in-memory repositories."""
    return UserService(
        user_repo=user_repo,
        profile_repo=profile_repo,
        security_port=security_adapter
    )


@pytest.fixture
def auth_service(user_repo, security_adapter):
    """Provides AuthService initialized with in-memory repositories."""
    return AuthService(
        user_repo=user_repo,
        security_port=security_adapter
    )


@pytest.fixture
def profile_service(profile_repo):
    """Provides ProfileService initialized with in-memory repositories."""
    return ProfileService(profile_repo=profile_repo)


@pytest.fixture
def test_users(user_service, security_adapter):
    """
    Pre-populates in-memory database with test users:
    - active_user: user@example.com / Password123!
    - inactive_user: inactive@example.com / Password123!
    - admin_user: admin@example.com / AdminPassword123!
    """
    from domain.models import UserCreate, ProfileBase

    # 1. Create Active User
    active_user = user_service.register_user(UserCreate(
        email="user@example.com",
        password="Password123!",
        profile=ProfileBase(name="Active Test User")
    ))

    # 2. Create Inactive User
    inactive_user = user_service.register_user(UserCreate(
        email="inactive@example.com",
        password="Password123!",
        profile=ProfileBase(name="Inactive Test User")
    ))
    user_service.update_user(inactive_user.id, {"is_active": False})
    inactive_user.is_active = False

    # 3. Create Admin User
    admin_user = user_service.register_user(UserCreate(
        email="admin@example.com",
        password="AdminPassword123!",
        profile=ProfileBase(name="Admin Test User")
    ))
    user_service.update_user(admin_user.id, {"role": "admin"})
    admin_user.role = "admin"

    # Pre-generate valid JWT tokens
    active_token = security_adapter.create_access_token(subject=active_user.id)
    admin_token = security_adapter.create_access_token(subject=admin_user.id)
    expired_token = security_adapter.create_access_token(subject=active_user.id, expires_delta_minutes=-10)

    return {
        "active": active_user,
        "active_raw_password": "Password123!",
        "active_token": active_token,
        "inactive": inactive_user,
        "inactive_raw_password": "Password123!",
        "admin": admin_user,
        "admin_raw_password": "AdminPassword123!",
        "admin_token": admin_token,
        "expired_token": expired_token
    }


@pytest.fixture
def client(user_service, auth_service, profile_service, security_adapter, test_users):
    """
    Provides FastAPI TestClient with dependency overrides wired to in-memory fixtures.
    """
    app.dependency_overrides[get_security_adapter_dep] = lambda: security_adapter
    app.dependency_overrides[get_user_service_dep] = lambda: user_service
    app.dependency_overrides[get_auth_service_dep] = lambda: auth_service
    app.dependency_overrides[get_profile_service_dep] = lambda: profile_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
