"""Unit tests for readability, relevance, and parallel evaluator (User Story 2 - T016)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_intake.rfp_generator_agents import WarehouseGeneratorAgent  # noqa: E402
from data.pipelines.rfp_response_generation.evaluator import (  # noqa: E402
    DepartmentSectionEvaluator,
    evaluate_readability,
    evaluate_relevance,
)


def test_evaluate_readability_passes_executive_draft() -> None:
    """Verify readability evaluation passes a clear executive proposal section draft."""
    agent = WarehouseGeneratorAgent()
    draft = agent.generate(
        rfp_metadata={"client_name": "ModaViva, S.L.", "client_country": "ES", "currency": "EUR"},
        section_context={
            "key_aspects": {
                "warehouse_location_preference": "Zaragoza",
                "sku_count": 300,
                "onboarding_complexity": "Baja",
            }
        },
    )
    res = evaluate_readability(draft)
    assert res.pass_status is True
    assert getattr(res, "pass") is True
    assert res.score >= 30.0
    assert "Flesch Reading Ease" in res.details


def test_evaluate_readability_fails_empty_or_too_short_draft() -> None:
    """Verify readability evaluation fails empty or trivial 3-word drafts."""
    empty_res = evaluate_readability("")
    assert empty_res.pass_status is False
    assert empty_res.score == 0.0

    short_res = evaluate_readability("Too short draft.")
    assert short_res.pass_status is False
    assert "too brief" in short_res.details.lower()


def test_evaluate_relevance_detects_missing_key_aspects() -> None:
    """Verify relevance evaluator flags missing Part 1 key_aspects."""
    key_aspects = {
        "warehouse_location_preference": "Zaragoza",
        "sku_count": 400,
        "onboarding_complexity": "Alta",
    }
    incomplete_draft = "We offer pallet storage in our Zaragoza warehouse facility."
    rel = evaluate_relevance(incomplete_draft, key_aspects=key_aspects)
    assert rel.pass_status is False
    assert "sku_count" in rel.missing_aspects
    assert "onboarding_complexity" in rel.missing_aspects


def test_department_section_evaluator_emits_structured_evaluation_result() -> None:
    """Verify DepartmentSectionEvaluator runs all 3 dimensions and matches schema contract."""
    agent = WarehouseGeneratorAgent()
    key_aspects = {
        "warehouse_location_preference": "Zaragoza",
        "pallet_storage_required": 200,
        "sku_count": 450,
        "special_handling": ["fashion_garments"],
        "onboarding_complexity": "Baja",
    }
    draft = agent.generate(
        rfp_metadata={"client_name": "ModaViva", "client_country": "ES", "currency": "EUR"},
        section_context={"key_aspects": key_aspects, "open_questions": []},
    )
    evaluator = DepartmentSectionEvaluator()
    result = evaluator.evaluate(
        department_id="warehouse",
        draft_text=draft,
        client_country="ES",
        key_aspects=key_aspects,
        iteration=1,
    )

    assert result.overall_pass is True
    assert result.readability.pass_status is True
    assert result.relevance.pass_status is True
    assert result.compliance.pass_status is True

    schema_dict = result.to_schema_dict()
    schema_path = (
        REPO_ROOT
        / "specs"
        / "032-rfp-response-generation"
        / "contracts"
        / "evaluation-result.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for req_key in schema["required"]:
        assert req_key in schema_dict
