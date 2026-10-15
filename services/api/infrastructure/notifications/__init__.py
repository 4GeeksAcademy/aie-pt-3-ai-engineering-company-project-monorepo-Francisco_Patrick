"""Notifications infrastructure package."""

from infrastructure.notifications.email_adapter import EmailAdapter, mask_email

__all__ = ["EmailAdapter", "mask_email"]
