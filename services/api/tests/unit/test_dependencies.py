"""Unit tests for presentation dependency injection providers."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from tinydb import TinyDB

from presentation.dependencies import (
    get_auth_service_dep,
    get_cache_dep,
    get_current_admin_user,
    get_current_user,
    get_incident_service_dep,
    get_profile_service_dep,
    get_security_adapter_dep,
    get_tinydb_dep,
    get_user_repository_dep,
    get_user_service_dep,
)
from domain.common.ports import CachePort
from domain.ports import SecurityPort
from application.services.auth_service import AuthService
from application.services.incident_service import IncidentService
from application.services.profile_service import ProfileService
from application.services.user_service import UserService


def test_dependency_providers_instantiation() -> None:
    # 1. Test TinyDB dependency
    db = get_tinydb_dep()
    assert isinstance(db, TinyDB)

    # 2. Test Security adapter dependency
    sec = get_security_adapter_dep()
    assert isinstance(sec, SecurityPort)

    # 3. Test Cache dependency
    cache = get_cache_dep()
    assert isinstance(cache, CachePort)

    # 4. Test Service dependencies with direct wiring
    user_repo = get_user_repository_dep(db)
    user_svc = get_user_service_dep(user_repo=user_repo, profile_repo=None, security_port=sec)
    assert isinstance(user_svc, UserService)

    auth_svc = get_auth_service_dep(user_repo=user_repo, security_port=sec)
    assert isinstance(auth_svc, AuthService)

    incident_svc = get_incident_service_dep(incident_repo=None)
    assert isinstance(incident_svc, IncidentService)


def test_dependency_injection_within_fastapi_app() -> None:
    test_app = FastAPI()

    @test_app.get("/test-di")
    def di_endpoint(
        cache: CachePort = Depends(get_cache_dep),
        sec: SecurityPort = Depends(get_security_adapter_dep),
    ):
        return {
            "cache_ready": cache is not None,
            "security_ready": sec is not None,
        }

    client = TestClient(test_app)
    res = client.get("/test-di")
    assert res.status_code == 200
    assert res.json() == {"cache_ready": True, "security_ready": True}
