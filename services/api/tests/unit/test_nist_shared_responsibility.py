"""Unit tests verifying third-party AI provider shared responsibility matrix boundaries (US1, FR-006)."""

import pytest
from infrastructure.adapters.nist_governance_repository import NISTGovernanceRepository
from presentation.schemas.security_audit import SharedResponsibilityRecordSchema


@pytest.fixture
def nist_repo() -> NISTGovernanceRepository:
    """Fixture providing a fresh NISTGovernanceRepository instance."""
    return NISTGovernanceRepository()


def test_shared_responsibility_matrix_completeness(nist_repo: NISTGovernanceRepository) -> None:
    """Verify that all external providers are mapped and conform to SharedResponsibilityRecordSchema."""
    records = nist_repo.list_shared_responsibility()
    assert len(records) >= 3, "Expected at least 3 third-party provider records"

    validated = [SharedResponsibilityRecordSchema.model_validate(r) for r in records]
    provider_ids = {r.provider_id for r in validated}

    assert "VEND-ANTHROPIC" in provider_ids
    assert "VEND-QDRANT" in provider_ids
    assert "VEND-COURIERS" in provider_ids


def test_shared_responsibility_vendor_boundaries_and_zero_retention(
    nist_repo: NISTGovernanceRepository,
) -> None:
    """Verify that providers enforce TLS 1.3 transit encryption, zero retention, and DPA agreements."""
    records = nist_repo.list_shared_responsibility()
    mapped = {r["provider_id"]: SharedResponsibilityRecordSchema.model_validate(r) for r in records}

    # 1. Foundation Model Provider (Anthropic)
    anthropic = mapped["VEND-ANTHROPIC"]
    assert anthropic.vendor_category == "FOUNDATION_MODEL_API"
    assert anthropic.zero_data_retention_active is True
    assert anthropic.transit_encryption_enforced is True
    assert "DPA" in anthropic.governing_dpa_reference
    assert len(anthropic.trackflow_responsibilities) > 0
    assert len(anthropic.vendor_responsibilities) > 0

    # 2. Vector DB Cloud (Qdrant)
    qdrant = mapped["VEND-QDRANT"]
    assert qdrant.vendor_category == "VECTOR_DATABASE_CLOUD"
    assert qdrant.zero_data_retention_active is True
    assert qdrant.transit_encryption_enforced is True
    assert "DPA" in qdrant.governing_dpa_reference

    # 3. Courier Integrations
    couriers = mapped["VEND-COURIERS"]
    assert couriers.vendor_category == "COURIER_CARRIER_INTEGRATION"
    assert couriers.transit_encryption_enforced is True
