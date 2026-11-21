"""Unit tests for Warehouse, Last Mile, and Reverse Logistics workers zero-hallucination guardrail."""

from uuid import uuid4
import pytest

from application.agent.rfp_department_workers import (
    LastMileWorker,
    ReverseWorker,
    WarehouseWorker,
)


def test_warehouse_worker_zero_hallucination_on_missing_pallets():
    """Verify WarehouseWorker does NOT invent pallet counts, recording in open_questions."""
    worker = WarehouseWorker()
    ticket_id = uuid4()
    text = (
        "# Proposal for Apparel Brand\n"
        "We need e-commerce warehousing in Zaragoza. "
        "No pallet dimensions or rack positions are specified."
    )

    section = worker.analyze(ticket_id, text, country="ES")

    assert section.department_id == "warehouse"
    assert section.responsible_person == "Ana Whitfield"
    assert section.key_aspects["warehouse_location_preference"] == "Zaragoza"
    assert section.key_aspects["pallet_storage_required"] is None
    # Zero hallucination guardrail: must record missing information
    assert len(section.open_questions) > 0
    assert any("pallet" in q.lower() or "posiciones" in q.lower() for q in section.open_questions)


def test_last_mile_worker_analyzes_domestic_and_sla():
    """Verify LastMileWorker captures carrier strategy and flags missing SLA."""
    worker = LastMileWorker()
    ticket_id = uuid4()
    text = (
        "# Last Mile Request\n"
        "Need deliveries across mainland Spain. Delivery timeframe not agreed yet."
    )

    section = worker.analyze(ticket_id, text, country="ES")

    assert section.department_id == "lastmile"
    assert section.responsible_person == "Carlos Vega"
    assert section.key_aspects["geographic_scope"] == "Domestic ES"
    assert section.key_aspects["delivery_sla_requested"] is None
    assert any("sla" in q.lower() for q in section.open_questions)


def test_reverse_worker_applies_30_day_policy_and_inspection():
    """Verify ReverseWorker enforces standard 30-day window, inspection flow, and policy warnings."""
    worker = ReverseWorker()
    ticket_id = uuid4()
    text = (
        "# Returns Specification\n"
        "Client demands 24h turnaround for all customer returns and exchanges."
    )

    section = worker.analyze(ticket_id, text, country="ES")

    assert section.department_id == "reverse"
    assert section.responsible_person == "Sofía Ramos"
    assert section.key_aspects["return_window_days"] == 30
    assert section.key_aspects["inspection_required"] is True
    # Should warn that < 48h turnaround conflicts with inspection policy
    assert len(section.policy_warnings) > 0
    assert any("48h" in w or "manual" in w.lower() for w in section.policy_warnings)
