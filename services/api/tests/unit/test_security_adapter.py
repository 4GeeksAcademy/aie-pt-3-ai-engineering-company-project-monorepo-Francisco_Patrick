import pytest
from domain.exceptions import AuthenticationError
from infrastructure.adapters.security_adapter import JwtSecurityAdapter


def test_hash_password_and_verify_success(security_adapter: JwtSecurityAdapter):
    """
    Happy Path: Password hashing generates a bcrypt hash and successfully verifies correct passwords.
    """
    raw_password = "MySecretPassword123!"
    hashed = security_adapter.hash_password(raw_password)

    assert hashed != raw_password
    assert security_adapter.verify_password(raw_password, hashed) is True
    assert security_adapter.verify_password("WrongPassword123!", hashed) is False


def test_create_and_decode_access_token_success(security_adapter: JwtSecurityAdapter):
    """
    Happy Path: Valid access token is created and decodes subject correctly.
    """
    subject_id = "usr_12345"
    token = security_adapter.create_access_token(subject=subject_id, expires_delta_minutes=15)

    assert isinstance(token, str)
    decoded_subject = security_adapter.decode_access_token(token)
    assert decoded_subject == subject_id


def test_decode_expired_token_raises_authentication_error(security_adapter: JwtSecurityAdapter):
    """
    Edge Case: Expired token raises AuthenticationError upon decoding.
    """
    subject_id = "usr_expired"
    expired_token = security_adapter.create_access_token(subject=subject_id, expires_delta_minutes=-5)

    with pytest.raises(AuthenticationError) as exc_info:
        security_adapter.decode_access_token(expired_token)

    assert "Could not validate credentials" in str(exc_info.value)


def test_decode_invalid_signature_raises_authentication_error(security_adapter: JwtSecurityAdapter):
    """
    Failure Mode: Token signed with different secret key raises AuthenticationError.
    """
    other_adapter = JwtSecurityAdapter()
    other_adapter.secret_key = "different-unauthorized-secret-key-32b"

    tampered_token = other_adapter.create_access_token(subject="usr_hacked")

    with pytest.raises(AuthenticationError) as exc_info:
        security_adapter.decode_access_token(tampered_token)

    assert "Could not validate credentials" in str(exc_info.value)
