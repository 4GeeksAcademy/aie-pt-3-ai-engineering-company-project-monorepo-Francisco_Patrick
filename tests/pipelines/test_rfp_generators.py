"""Unit tests for department proposal generator agents (User Story 1 - T009)."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_intake.rfp_generator_agents import (  # noqa: E402
    LastMileGeneratorAgent,
    ReverseLogisticsGeneratorAgent,
    WarehouseGeneratorAgent,
    get_department_generator_agent,
)


def test_warehouse_generator_modaviva_spain_eur_draft() -> None:
    """Verify WarehouseGeneratorAgent produces a compliant EUR draft for ModaViva Spain without PDF re-parsing."""
    agent = WarehouseGeneratorAgent()
    rfp_metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "ES",
        "currency": "EUR",
        "monthly_volume": 3500,
        "departments_needed": ["warehouse", "reverse"],
    }
    section_context = {
        "department_id": "warehouse",
        "key_aspects": {
            "warehouse_location_preference": "Zaragoza",
            "pallet_storage_required": None,
            "sku_count": 450,
            "special_handling": ["fashion_garments"],
            "onboarding_complexity": "Baja",
        },
        "open_questions": [
            "Número exacto de pallets o posiciones de estantería requeridas no especificado en la propuesta."
        ],
    }

    draft = agent.generate(rfp_metadata, section_context, iteration=1)

    assert "ModaViva, S.L." in draft
    assert "Ana Whitfield" in draft
    assert "Zaragoza" in draft
    assert "450" in draft
    assert "EUR" in draft
    assert "USD" not in draft
    assert "90%" in draft
    assert "16.00 EUR por m³" in draft
    assert "Miguel Torres" in draft
    assert "Pendiente" in draft
    assert "Volume Discount" in draft
    assert "Open Questions" in draft


def test_lastmile_generator_luna_cosmetics_us_usd_draft() -> None:
    """Verify LastMileGeneratorAgent produces a compliant USD draft for Luna Cosmetics US."""
    agent = LastMileGeneratorAgent()
    rfp_metadata = {
        "client_name": "Luna Cosmetics",
        "client_country": "US",
        "currency": "USD",
        "monthly_volume": 5000,
        "departments_needed": ["warehouse", "lastmile"],
    }
    section_context = {
        "department_id": "lastmile",
        "key_aspects": {
            "carrier_strategy": "TrackFlow Network",
            "geographic_scope": "Domestic US",
            "delivery_sla_requested": "48-72h",
            "special_delivery_requirements": ["signature_on_delivery"],
        },
        "open_questions": [],
    }

    draft = agent.generate(rfp_metadata, section_context, iteration=1)

    assert "Luna Cosmetics" in draft
    assert "Carlos Vega" in draft
    assert "Domestic US" in draft
    assert "USD" in draft
    assert "EUR" not in draft
    assert "90%" in draft
    assert "Miguel Torres" in draft
    assert "Volume Discount" in draft


def test_reverse_generator_enforces_48h_minimum_turnaround() -> None:
    """Verify ReverseLogisticsGeneratorAgent commits to >= 48h turnaround in EUR for Spain."""
    agent = ReverseLogisticsGeneratorAgent()
    rfp_metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "ES",
        "currency": "EUR",
        "departments_needed": ["warehouse", "reverse"],
    }
    section_context = {
        "department_id": "reverse",
        "key_aspects": {
            "return_window_days": 30,
            "estimated_return_rate": 0.18,
            "inspection_required": True,
            "disposition_flow": ["reventa", "reacondicionamiento", "descarte"],
        },
        "open_questions": [],
    }

    draft = agent.generate(rfp_metadata, section_context, iteration=1)

    assert "Sofía Ramos" in draft
    assert "48 to 72 hours" in draft
    assert "EUR" in draft
    assert "90%" in draft
    assert "Miguel Torres" in draft
    assert "30 days" in draft


def test_factory_get_department_generator_agent() -> None:
    """Verify factory returns dedicated agent instances for warehouse, lastmile, and reverse."""
    assert isinstance(get_department_generator_agent("warehouse"), WarehouseGeneratorAgent)
    assert isinstance(get_department_generator_agent("lastmile"), LastMileGeneratorAgent)
    assert isinstance(get_department_generator_agent("reverse"), ReverseLogisticsGeneratorAgent)
