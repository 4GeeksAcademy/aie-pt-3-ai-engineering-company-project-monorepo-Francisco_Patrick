"""Integration tests for Part 3 handoff payload compilation and schema validation (User Story 4 - T030)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_response_generation.pipeline import (  # noqa: E402
    RFPResponseGenerationPipeline,
)


def test_part3_handoff_payload_matches_json_schema_contract() -> None:
    """Verify compiled Part 3 handoff payload strictly satisfies part3-handoff.schema.json."""
    pipeline = RFPResponseGenerationPipeline()
    ticket_id = uuid4()
    rfp_metadata = {
        "client_name": "Luna Cosmetics",
        "client_country": "US",
        "currency": "USD",
        "monthly_volume": 5000,
        "deadline": "2026-12-01",
        "departments_needed": ["warehouse", "lastmile"],
    }
    department_sections = {
        "warehouse": {
            "department_id": "warehouse",
            "key_aspects": {
                "warehouse_location_preference": "Los Ángeles",
                "pallet_storage_required": 150,
                "sku_count": 85,
                "special_handling": ["cosmetics_storage"],
                "onboarding_complexity": "Alta",
            },
            "open_questions": [
                "Transición desde garaje/espacio informal requiere inventario inicial ciego."
            ],
        },
        "lastmile": {
            "department_id": "lastmile",
            "key_aspects": {
                "carrier_strategy": "TrackFlow Network",
                "geographic_scope": "Domestic US",
                "delivery_sla_requested": "48-72h",
                "special_delivery_requirements": [],
            },
            "open_questions": [],
        },
    }

    handoff = pipeline.execute_from_handoff(
        ticket_id=ticket_id,
        rfp_metadata=rfp_metadata,
        department_sections=department_sections,
    )
    handoff_dict = handoff.to_schema_dict()

    schema_path = (
        REPO_ROOT
        / "specs"
        / "032-rfp-response-generation"
        / "contracts"
        / "part3-handoff.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Validate top-level required fields and allowed properties
    for req_field in schema["required"]:
        assert req_field in handoff_dict
    assert set(handoff_dict.keys()).issubset(set(schema["properties"].keys()))

    assert handoff_dict["ticket_id"] == str(ticket_id)
    assert handoff_dict["schema_version"] == "2.0.0"
    assert handoff_dict["overall_status"] == "passed"
    assert handoff_dict["rfp_metadata"]["client_country"] == "US"
    assert handoff_dict["rfp_metadata"]["currency"] == "USD"
    assert set(handoff_dict["department_sections"].keys()) == {"warehouse", "lastmile"}

    for dept_id, bundle in handoff_dict["department_sections"].items():
        assert set(bundle.keys()) == {
            "draft_content",
            "status",
            "iteration",
            "evaluation_result",
        }
        assert bundle["status"] == "passed"
        assert 1 <= bundle["iteration"] <= 3
        assert bundle["evaluation_result"]["department_id"] == dept_id
        assert bundle["evaluation_result"]["overall_pass"] is True
