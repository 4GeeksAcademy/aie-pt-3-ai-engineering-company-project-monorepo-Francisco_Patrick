"""Unit test verifying PII and carrier credential masking in audit logging (T028)."""

import pytest
from application.services.guardrail_observability import sanitize_audit_preview


def test_carrier_credentials_masking() -> None:
    """Verify that carrier credentials for UPS, FedEx, DHL, MRW, and SEUR are masked."""
    test_cases = [
        ("Using UPS_KEY: ups_sec_994821a8f9 for shipping label", "[REDACTED_CARRIER_CREDENTIAL]"),
        ("FedEx credentials: FEDEX_METER=8492019 and FEDEX_KEY=fx_live_9921", "[REDACTED_CARRIER_CREDENTIAL]"),
        ("DHL account access token dhl_token_secret_1234567890", "[REDACTED_CARRIER_CREDENTIAL]"),
        ("MRW authorization: mrw_api_key=mrw_secret_88192", "[REDACTED_CARRIER_CREDENTIAL]"),
        ("SEUR webhook signing secret: seur_secret=seur_live_key_999", "[REDACTED_CARRIER_CREDENTIAL]"),
    ]

    for raw, expected_token in test_cases:
        sanitized = sanitize_audit_preview(raw)
        assert expected_token in sanitized, f"Failed to mask in: {raw} -> {sanitized}"
        # Ensure raw secret token is completely absent
        assert "ups_sec_" not in sanitized
        assert "fx_live_" not in sanitized
        assert "dhl_token_secret_" not in sanitized
        assert "mrw_secret_" not in sanitized
        assert "seur_live_key_" not in sanitized


def test_customer_pii_and_auth_token_masking() -> None:
    """Verify customer PII and bearer tokens are redacted."""
    raw = "Customer John Doe with email john.doe@example.com and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
    sanitized = sanitize_audit_preview(raw)
    assert "[REDACTED_EMAIL]" in sanitized
    assert "john.doe@example.com" not in sanitized
    assert "[REDACTED_AUTH_TOKEN]" in sanitized or "[REDACTED_CARRIER_CREDENTIAL]" in sanitized or "Bearer" not in sanitized
