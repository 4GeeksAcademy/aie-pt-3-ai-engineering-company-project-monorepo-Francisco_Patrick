import pytest
from domain.exceptions import AuthenticationError, UserInactiveError
from application.services.auth_service import AuthService, mask_email
from application.services.email_service import EmailService
from infrastructure.middleware.rate_limiter import RateLimiter


def test_mask_email_utility():
    """
    Utility Test: Verifies email PII masking for audit logs.
    """
    assert mask_email("user@example.com") == "u***r@example.com"
    assert mask_email("a@b.com") == "a***@b.com"
    assert mask_email("") == "***"


def test_authenticate_user_happy_path(auth_service: AuthService, test_users):
    """
    Happy Path: Valid active user credentials return a valid JWT access token.
    """
    email = test_users["active"].email
    password = test_users["active_raw_password"]

    token = auth_service.authenticate_user(email=email, password=password)

    assert isinstance(token, str)
    decoded_sub = auth_service.security_port.decode_access_token(token)
    assert decoded_sub == test_users["active"].id


def test_authenticate_user_inactive_raises_user_inactive_error(auth_service: AuthService, test_users):
    """
    Edge Case: Inactive user account credentials raise UserInactiveError.
    """
    email = test_users["inactive"].email
    password = test_users["inactive_raw_password"]

    with pytest.raises(UserInactiveError) as exc_info:
        auth_service.authenticate_user(email=email, password=password)

    assert "User account is inactive" in str(exc_info.value)


def test_authenticate_user_invalid_password_raises_authentication_error(auth_service: AuthService, test_users):
    """
    Failure Mode: Wrong password for registered email raises AuthenticationError without leaking specific detail.
    """
    email = test_users["active"].email

    with pytest.raises(AuthenticationError) as exc_info:
        auth_service.authenticate_user(email=email, password="WrongPassword123!")

    assert "Invalid email or password" in str(exc_info.value)


def test_authenticate_user_nonexistent_email_raises_authentication_error(auth_service: AuthService):
    """
    Failure Mode: Non-existent email raises AuthenticationError.
    """
    with pytest.raises(AuthenticationError) as exc_info:
        auth_service.authenticate_user(email="nonexistent@example.com", password="Password123!")

    assert "Invalid email or password" in str(exc_info.value)


def test_request_password_reset_registered_email(auth_service: AuthService, token_repo, audit_repo, test_users):
    """
    Happy Path: Password reset request for registered user creates reset token record.
    """
    email_service = EmailService()
    rate_limiter = RateLimiter()

    res = auth_service.request_password_reset(
        email=test_users["active"].email,
        token_repo=token_repo,
        audit_repo=audit_repo,
        email_service=email_service,
        rate_limiter=rate_limiter
    )

    assert res["message"] == "If that email is registered, you will receive a reset link shortly."


def test_request_password_reset_unregistered_email_anti_enumeration(auth_service: AuthService, token_repo, audit_repo):
    """
    Edge Case: Password reset request for unregistered email returns generic message without throwing error.
    """
    email_service = EmailService()
    rate_limiter = RateLimiter()

    res = auth_service.request_password_reset(
        email="unregistered@example.com",
        token_repo=token_repo,
        audit_repo=audit_repo,
        email_service=email_service,
        rate_limiter=rate_limiter
    )

    assert res["message"] == "If that email is registered, you will receive a reset link shortly."


def test_reset_password_success_and_single_use(auth_service: AuthService, token_repo, audit_repo, test_users, monkeypatch):
    """
    Happy Path & Edge Case: Reset password updates user password and marks token as used (single use).
    """
    email_service = EmailService()
    rate_limiter = RateLimiter()
    fixed_token = "unit_test_fixed_raw_token_string"

    import secrets
    monkeypatch.setattr(secrets, "token_urlsafe", lambda n=32: fixed_token)

    # Create token
    auth_service.request_password_reset(
        email=test_users["active"].email,
        token_repo=token_repo,
        audit_repo=audit_repo,
        email_service=email_service,
        rate_limiter=rate_limiter
    )

    # Reset password
    res = auth_service.reset_password(
        raw_token=fixed_token,
        new_password="NewResetPassword123!",
        token_repo=token_repo,
        audit_repo=audit_repo
    )
    assert res["message"] == "Password successfully updated."

    # Attempting reset with same token again raises AuthenticationError
    with pytest.raises(AuthenticationError) as exc_info:
        auth_service.reset_password(
            raw_token=fixed_token,
            new_password="AnotherPassword123!",
            token_repo=token_repo,
            audit_repo=audit_repo
        )
    assert "Invalid, expired, or already used reset token" in str(exc_info.value)
