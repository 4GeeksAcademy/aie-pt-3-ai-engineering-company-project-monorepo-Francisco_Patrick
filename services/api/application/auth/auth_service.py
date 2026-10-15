"""Authentication application service managing credentials, tokens, and password recovery."""

import secrets
from typing import Any, Dict, Optional

from domain.auth.ports import (
    AuditLogRepositoryPort,
    PasswordResetTokenRepositoryPort,
    SecurityPort,
    UserRepositoryPort,
)
from domain.common.exceptions import AuthenticationError, UserInactiveError
from domain.common.ports import NotificationPort


def mask_email(email: str) -> str:
    """Mask email address PII for safe logging."""
    if not email or "@" not in email:
        return "***"
    parts = email.split("@", 1)
    name = parts[0]
    domain = parts[1]
    masked_name = name[0] + "***" + name[-1] if len(name) > 2 else name[0] + "***"
    return f"{masked_name}@{domain}"


class AuthService:
    """Application use case service orchestrating authentication and password workflows."""

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        security_port: SecurityPort,
        token_repo: Optional[PasswordResetTokenRepositoryPort] = None,
        audit_repo: Optional[AuditLogRepositoryPort] = None,
        notification_port: Optional[NotificationPort] = None,
    ) -> None:
        """Initialize service with injected driven ports."""
        self.user_repo = user_repo
        self.security_port = security_port
        self.token_repo = token_repo
        self.audit_repo = audit_repo
        self.notification_port = notification_port

    def authenticate_user(self, email: str, password: str) -> str:
        """Validate user credentials and return signed JWT access token.

        Raises:
            AuthenticationError: If email or password is invalid.
            UserInactiveError: If user account is marked inactive.
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            raise AuthenticationError("Invalid email or password")

        # user may be domain User entity or legacy dict
        hashed_pw = user.hashed_password if hasattr(user, "hashed_password") else user.get("hashed_password", "")
        user_id = user.id if hasattr(user, "id") else user.get("id", "")
        is_active = user.is_active if hasattr(user, "is_active") else user.get("is_active", True)

        if not self.security_port.verify_password(password, hashed_pw):
            raise AuthenticationError("Invalid email or password")

        if not is_active:
            raise UserInactiveError("User account is inactive")

        return self.security_port.create_access_token(subject=user_id)

    def request_password_reset(
        self,
        email: str,
        token_repo: Optional[Any] = None,
        audit_repo: Optional[Any] = None,
        email_service: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        ip_address: str = "127.0.0.1",
        base_url: str = "http://localhost:3000",
    ) -> Dict[str, str]:
        """Process password reset request adhering to anti-enumeration principles."""
        active_token_repo = token_repo or self.token_repo
        active_audit_repo = audit_repo or self.audit_repo
        active_notifier = email_service or self.notification_port

        masked = mask_email(email)

        if rate_limiter and rate_limiter.is_rate_limited(email):
            if active_audit_repo:
                active_audit_repo.log_event(
                    "forgot_password_request_rate_limited",
                    None,
                    ip_address,
                    f"Email: {masked}",
                )
            return {
                "message": "If that email is registered, you will receive a reset link shortly."
            }

        user = self.user_repo.get_by_email(email)
        if not user:
            if active_audit_repo:
                active_audit_repo.log_event(
                    "forgot_password_request_unregistered",
                    None,
                    ip_address,
                    f"Email: {masked}",
                )
            return {
                "message": "If that email is registered, you will receive a reset link shortly."
            }

        user_id = user.id if hasattr(user, "id") else user.get("id", "")
        raw_token = secrets.token_urlsafe(32)

        if active_token_repo:
            active_token_repo.create_token(
                user_id=user_id, raw_token=raw_token, expires_in_minutes=30
            )

        if active_audit_repo:
            active_audit_repo.log_event(
                "forgot_password_request_success",
                user_id,
                ip_address,
                f"Email: {masked}",
            )

        reset_link = f"{base_url}/reset-password?token={raw_token}"
        if active_notifier:
            try:
                if hasattr(active_notifier, "send_password_reset"):
                    active_notifier.send_password_reset(email, reset_link)
                elif hasattr(active_notifier, "send_password_reset_email"):
                    active_notifier.send_password_reset_email(email, reset_link)
            except Exception:
                if active_audit_repo:
                    active_audit_repo.log_event(
                        "forgot_password_email_dispatch_failed",
                        user_id,
                        ip_address,
                        f"Email dispatch failed for {masked}",
                    )

        return {
            "message": "If that email is registered, you will receive a reset link shortly."
        }

    def reset_password(
        self,
        raw_token: str,
        new_password: str,
        token_repo: Optional[Any] = None,
        audit_repo: Optional[Any] = None,
        ip_address: str = "127.0.0.1",
    ) -> Dict[str, str]:
        """Validate reset token and update user credentials."""
        active_token_repo = token_repo or self.token_repo
        active_audit_repo = audit_repo or self.audit_repo

        token_doc = active_token_repo.get_valid_token(raw_token) if active_token_repo else None
        if not token_doc:
            if active_audit_repo:
                active_audit_repo.log_event(
                    "password_reset_failed",
                    None,
                    ip_address,
                    "Invalid or expired token",
                )
            raise AuthenticationError("Invalid, expired, or already used reset token.")

        user_id = token_doc["user_id"]
        hashed_password = self.security_port.hash_password(new_password)

        if hasattr(self.user_repo, "update"):
            self.user_repo.update(user_id, {"hashed_password": hashed_password})
        else:
            user = self.user_repo.get_by_id(user_id)
            if user:
                user.hashed_password = hashed_password
                self.user_repo.save(user)

        if active_token_repo:
            active_token_repo.mark_used(token_doc["id"])

        if active_audit_repo:
            active_audit_repo.log_event(
                "password_reset_success",
                user_id,
                ip_address,
                "Password successfully reset",
            )

        return {"message": "Password successfully updated."}

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        audit_repo: Optional[Any] = None,
        ip_address: str = "127.0.0.1",
    ) -> Dict[str, str]:
        """Update password for authenticated user after verifying existing credentials."""
        active_audit_repo = audit_repo or self.audit_repo
        user = self.user_repo.get_by_id(user_id)

        if not user:
            if active_audit_repo:
                active_audit_repo.log_event(
                    "password_change_failed", user_id, ip_address, "User not found"
                )
            raise AuthenticationError("User not found")

        hashed_pw = user.hashed_password if hasattr(user, "hashed_password") else user.get("hashed_password", "")
        if not self.security_port.verify_password(current_password, hashed_pw):
            if active_audit_repo:
                active_audit_repo.log_event(
                    "password_change_failed",
                    user_id,
                    ip_address,
                    "Incorrect current password",
                )
            raise AuthenticationError("Incorrect current password.")

        new_hashed = self.security_port.hash_password(new_password)
        if hasattr(self.user_repo, "update"):
            self.user_repo.update(user_id, {"hashed_password": new_hashed})
        else:
            user.hashed_password = new_hashed
            self.user_repo.save(user)

        if active_audit_repo:
            active_audit_repo.log_event(
                "password_change_success",
                user_id,
                ip_address,
                "Password successfully changed",
            )

        return {"message": "Password successfully changed."}


__all__ = ["AuthService", "mask_email"]
