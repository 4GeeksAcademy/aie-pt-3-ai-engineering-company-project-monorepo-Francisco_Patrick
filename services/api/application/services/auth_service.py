from typing import Optional
from domain.ports import UserRepositoryPort, SecurityPort
from domain.exceptions import AuthenticationError, UserInactiveError

class AuthService:
    def __init__(
        self,
        user_repo: UserRepositoryPort,
        security_port: SecurityPort
    ):
        self.user_repo = user_repo
        self.security_port = security_port

    def authenticate_user(self, email: str, password: str) -> str:
        """
        Validates credentials and returns a JWT access token.
        Raises AuthenticationError if invalid, or UserInactiveError if user is inactive.
        """
        user_data = self.user_repo.get_by_email(email)
        if not user_data:
            raise AuthenticationError("Invalid email or password")

        if not self.security_port.verify_password(password, user_data["hashed_password"]):
            raise AuthenticationError("Invalid email or password")

        if not user_data.get("is_active", True):
            raise UserInactiveError("User account is inactive")

        # Create token using the user's ID as the subject
        return self.security_port.create_access_token(subject=user_data["id"])

    def request_password_reset(
        self,
        email: str,
        token_repo,
        audit_repo,
        email_service,
        rate_limiter,
        ip_address: str = "127.0.0.1",
        base_url: str = "http://localhost:3000"
    ) -> dict:
        """
        Processes password reset request. Always returns a generic success message (anti-enumeration).
        """
        if rate_limiter.is_rate_limited(email):
            audit_repo.log_event("forgot_password_request_rate_limited", None, ip_address, f"Email: {email}")
            # Anti-enumeration requirement: do not fail explicitly or leak, but limit execution
            return {"message": "If that email is registered, you will receive a reset link shortly."}

        user_data = self.user_repo.get_by_email(email)
        if not user_data:
            audit_repo.log_event("forgot_password_request_unregistered", None, ip_address, f"Email: {email}")
            return {"message": "If that email is registered, you will receive a reset link shortly."}

        import secrets
        raw_token = secrets.token_urlsafe(32)
        token_repo.create_token(user_id=user_data["id"], raw_token=raw_token, expires_in_minutes=30)
        audit_repo.log_event("forgot_password_request_success", user_data["id"], ip_address, f"Email: {email}")

        reset_link = f"{base_url}/reset-password?token={raw_token}"
        email_service.send_password_reset_email(email, reset_link)

        return {"message": "If that email is registered, you will receive a reset link shortly."}

    def reset_password(
        self,
        raw_token: str,
        new_password: str,
        token_repo,
        audit_repo,
        ip_address: str = "127.0.0.1"
    ) -> dict:
        """
        Validates reset token and updates user password. Invalidates token upon success.
        """
        token_doc = token_repo.get_valid_token(raw_token)
        if not token_doc:
            audit_repo.log_event("password_reset_failed", None, ip_address, "Invalid or expired token")
            raise AuthenticationError("Invalid, expired, or already used reset token.")

        user_id = token_doc["user_id"]
        hashed_password = self.security_port.hash_password(new_password)
        self.user_repo.update(user_id, {"hashed_password": hashed_password})
        token_repo.mark_used(token_doc["id"])

        audit_repo.log_event("password_reset_success", user_id, ip_address, "Password successfully reset")
        return {"message": "Password successfully updated."}

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        audit_repo,
        ip_address: str = "127.0.0.1"
    ) -> dict:
        """
        Changes password for authenticated user after verifying current password.
        """
        user_data = self.user_repo.get_by_id(user_id)
        if not user_data:
            audit_repo.log_event("password_change_failed", user_id, ip_address, "User not found")
            raise AuthenticationError("User not found")

        if not self.security_port.verify_password(current_password, user_data["hashed_password"]):
            audit_repo.log_event("password_change_failed", user_id, ip_address, "Incorrect current password")
            raise AuthenticationError("Incorrect current password.")

        hashed_password = self.security_port.hash_password(new_password)
        self.user_repo.update(user_id, {"hashed_password": hashed_password})

        audit_repo.log_event("password_change_success", user_id, ip_address, "Password successfully changed")
        return {"message": "Password successfully changed."}



