"""Unit and integration tests for User Stories 5 & 6: Automatic Final Document Synthesis, Ticket Completion, and Execution Traceability (T034, T035, T036, T042)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest

from application.agent.rfp_approval_service import RFPApprovalService
from data.pipelines.rfp_approval_completion.state import (
    COMMERCIAL_DIRECTOR,
    SqliteSaver,
)
from data.pipelines.rfp_approval_completion.synthesis import (
    can_synthesize_final_document,
    synthesize_final_document,
)
from domain.rfp.entities import (
    DepartmentSection,
    IntakeTicket,
    ReadabilityScores,
    RFPMetadata,
    TicketStatus,
)
from infrastructure.persistence.sqlmodel.rfp_repository import (
    SQLModelIntakeTicketRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FINAL_DOC_SCHEMA_PATH = (
    REPO_ROOT
    / "specs"
    / "033-rfp-approval-completion"
    / "contracts"
    / "final-document.schema.json"
)


def _load_final_document_schema() -> dict:
    with open(FINAL_DOC_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_synthesis_gate_condition_blocks_partial_approvals() -> None:
    """T034 [US5]: Verify final document synthesis is strictly blocked until 100% of active departments have approved."""
    active_depts = ["warehouse", "lastmile", "reverse"]
    partial_sections = {
        "warehouse": {
            "department_name": "Warehouse Operations",
            "responsible_person": "Ana Whitfield",
            "draft_content": "Approved warehouse section",
            "approval_status": "approved",
        },
        "lastmile": {
            "department_name": "Last Mile",
            "responsible_person": "Carlos Vega",
            "draft_content": "Pending lastmile section",
            "approval_status": "pending",
        },
        "reverse": {
            "department_name": "Reverse Logistics",
            "responsible_person": "Sofía Ramos",
            "draft_content": "Approved reverse section",
            "approval_status": "approved",
        },
    }

    assert can_synthesize_final_document(active_depts, partial_sections) is False

    with pytest.raises(ValueError, match="not yet approved"):
        synthesize_final_document(
            ticket_id=uuid4(),
            rfp_metadata={"client_name": "ModaViva", "client_country": "ES"},
            department_sections=partial_sections,
            active_departments=active_depts,
        )

    # Once lastmile also approves, synthesis gate opens
    partial_sections["lastmile"]["approval_status"] = "approved"
    assert can_synthesize_final_document(active_depts, partial_sections) is True


def test_final_document_compilation_executive_summary_and_currency_binding() -> None:
    """T035 [US5]: Verify FinalDocument compiles all approved sections, binds canonical country currency, and validates against final-document.schema.json."""
    ticket_id = uuid4()
    meta = {
        "client_name": "Luna Cosmetics Inc.",
        "client_country": "US",
        "currency": "USD",
        "monthly_volume": 6500,
        "deadline": "2026-12-31",
        "departments_needed": ["warehouse", "lastmile"],
    }
    sections = {
        "warehouse": {
            "department_name": "Warehouse Operations",
            "responsible_person": "Ana Whitfield",
            "draft_content": "## Warehouse Proposal\nAll rates in USD ($18.00 USD). 99.2% SLA.",
            "approval_status": "approved",
            "approver": "Ana Whitfield",
            "approved_at": "2026-11-22T10:30:00+00:00",
        },
        "lastmile": {
            "department_name": "Last Mile and Carrier Management",
            "responsible_person": "Carlos Vega",
            "draft_content": "## Last Mile Proposal\nAll rates in USD ($6.40 USD). 98.5% SLA.",
            "approval_status": "approved",
            "approver": "Carlos Vega",
            "approved_at": "2026-11-22T10:35:00+00:00",
        },
    }

    final_doc = synthesize_final_document(
        ticket_id=ticket_id,
        rfp_metadata=meta,
        department_sections=sections,
        active_departments=["warehouse", "lastmile"],
    )

    assert final_doc.ticket_id == ticket_id
    assert final_doc.client_name == "Luna Cosmetics Inc."
    assert final_doc.currency == "USD"
    assert COMMERCIAL_DIRECTOR in final_doc.executive_summary
    assert "Ana Whitfield" in final_doc.executive_summary
    assert "Carlos Vega" in final_doc.executive_summary
    assert set(final_doc.sections.keys()) == {"warehouse", "lastmile"}

    schema = _load_final_document_schema()
    jsonschema.validate(instance=final_doc.to_schema_dict(), schema=schema)


def test_automatic_final_synthesis_and_ticket_status_terminado_preserving_fields(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T036 [US5]: Verify approving the final pending department automatically triggers FinalDocument persistence, transitions ticket to 'terminado', and preserves all Part 1 & Part 2 fields."""
    ticket_id = uuid4()
    raw_pdf_path = "data/raw/trackflow-request-1.pdf"
    ticket = IntakeTicket.create(
        raw_pdf_path=raw_pdf_path,
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=5120,
        ticket_id=ticket_id,
    )
    ticket.mark_under_evaluation()
    rfp_repository.save_ticket(ticket)

    expected_scores = ReadabilityScores(
        flesch_reading_ease=63.4,
        flesch_kincaid_grade=8.3,
        reading_level_label="Standard",
        word_count=512,
        sentence_count=28,
    )
    rfp_repository.save_metadata(
        RFPMetadata(
            id=uuid4(),
            ticket_id=ticket_id,
            client_name="ModaViva, S.L.",
            client_country="ES",
            currency="EUR",
            services_requested=["warehousing", "returns"],
            monthly_volume=3500,
            deadline="2026-12-15",
            budget_range="30,000 EUR",
            departments_needed=["warehouse", "reverse"],
            unsupported_services=[],
            readability_scores=expected_scores,
        )
    )

    wh_eval = [
        {
            "department_id": "warehouse",
            "iteration": 1,
            "readability": {"pass_status": True, "score": 65.0, "details": "Clear"},
            "relevance": {"pass_status": True, "missing_aspects": []},
            "compliance": {"pass_status": True, "rule_ids": [], "violations": []},
            "overall_pass": True,
            "feedback_for_generator": "",
            "evaluated_at": "2026-11-22T09:00:00+00:00",
        }
    ]
    rev_eval = [
        {
            "department_id": "reverse",
            "iteration": 1,
            "readability": {"pass_status": True, "score": 66.0, "details": "Clear"},
            "relevance": {"pass_status": True, "missing_aspects": []},
            "compliance": {"pass_status": True, "rule_ids": [], "violations": []},
            "overall_pass": True,
            "feedback_for_generator": "",
            "evaluated_at": "2026-11-22T09:01:00+00:00",
        }
    ]

    rfp_repository.save_department_section(
        DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="warehouse",
            department_name="Warehouse Operations",
            responsible_person="Ana Whitfield",
            key_aspects={"warehouse_location_preference": "Zaragoza", "sku_count": 300},
            open_questions=["Confirm pallet height"],
            policy_warnings=[],
            draft_content="## Warehouse Proposal for ModaViva\nAll prices in EUR (16.50 EUR). 99.2% SLA. 48 to 72 hours.",
            iteration=1,
            status="passed",
            evaluation_results=wh_eval,
        )
    )
    rfp_repository.save_department_section(
        DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="reverse",
            department_name="Reverse Logistics",
            responsible_person="Sofía Ramos",
            key_aspects={"return_window_days": 30},
            open_questions=[],
            policy_warnings=[],
            draft_content="## Reverse Proposal for ModaViva\nAll prices in EUR (2.40 EUR). 99.0% SLA. 48 to 72 hours turnaround.",
            iteration=1,
            status="passed",
            evaluation_results=rev_eval,
        )
    )

    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )
    service.enter_approval_milestone(ticket_id)

    # 1. Ana Whitfield approves warehouse -> ticket remains in esperando_aprobación
    res_wh = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="approve",
        approver="Ana Whitfield",
    )
    assert res_wh["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value
    assert rfp_repository.get_final_document(ticket_id) is None

    # 2. Sofía Ramos approves reverse -> 100% approved -> automatic FinalDocument synthesis & terminado!
    res_rev = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="reverse",
        decision="approve",
        approver="Sofía Ramos",
    )
    assert res_rev["approval_status"] == "approved"
    assert res_rev["ticket_status"] == TicketStatus.TERMINADO.value
    assert res_rev["final_document"] is not None

    # Verify FinalDocument persisted in PostgreSQL/SQLite repository
    persisted_doc = rfp_repository.get_final_document(ticket_id)
    assert persisted_doc is not None
    assert persisted_doc.client_name == "ModaViva, S.L."
    assert persisted_doc.currency == "EUR"
    assert "warehouse" in persisted_doc.sections
    assert "reverse" in persisted_doc.sections

    # Verify ticket status and complete preservation of Part 1 & Part 2 fields
    completed_ticket = rfp_repository.get_ticket(ticket_id)
    assert completed_ticket is not None
    assert completed_ticket.status == TicketStatus.TERMINADO
    assert completed_ticket.raw_pdf_path == raw_pdf_path
    assert completed_ticket.file_size_bytes == 5120

    preserved_meta = rfp_repository.get_metadata(ticket_id)
    assert preserved_meta is not None
    assert preserved_meta.readability_scores == expected_scores
    assert preserved_meta.budget_range == "30,000 EUR"

    wh_after = rfp_repository.get_department_section(ticket_id, "warehouse")
    assert wh_after is not None
    assert wh_after.key_aspects["warehouse_location_preference"] == "Zaragoza"
    assert wh_after.open_questions == ["Confirm pallet height"]
    assert len(wh_after.evaluation_results) == 1


def test_execution_trace_recording_across_nodes(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T042 [US6]: Verify every executed node appends a structured trace record with node_name, input_state, output_state, and ISO timestamp."""
    ticket_id = uuid4()
    ticket = IntakeTicket.create(
        raw_pdf_path="data/raw/trackflow-request-1.pdf",
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=2048,
        ticket_id=ticket_id,
    )
    rfp_repository.save_ticket(ticket)
    rfp_repository.save_metadata(
        RFPMetadata(
            id=uuid4(),
            ticket_id=ticket_id,
            client_name="ModaViva, S.L.",
            client_country="ES",
            currency="EUR",
            services_requested=["warehousing"],
            monthly_volume=2000,
            deadline=None,
            budget_range=None,
            departments_needed=["warehouse"],
            unsupported_services=[],
            readability_scores=ReadabilityScores(65.0, 8.0, "Standard", 250, 15),
        )
    )
    rfp_repository.save_department_section(
        DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="warehouse",
            department_name="Warehouse Operations",
            responsible_person="Ana Whitfield",
            key_aspects={},
            open_questions=[],
            policy_warnings=[],
            draft_content="## Warehouse Draft in EUR (16.50 EUR). 99.2% SLA. 48 to 72 hours.",
            iteration=1,
            status="passed",
        )
    )

    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )
    start_res = service.enter_approval_milestone(ticket_id)
    assert len(start_res["execution_trace"]) >= 1
    assert start_res["execution_trace"][0]["node_name"] == "prepare_branch_review"

    resume_res = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="approve",
        approver="Ana Whitfield",
    )
    traces = resume_res["execution_trace"]
    recorded_nodes = [t["node_name"] for t in traces]
    assert "prepare_branch_review" in recorded_nodes
    assert "human_approval_checkpoint" in recorded_nodes
    assert "finalize_branch_approval" in recorded_nodes

    for entry in traces:
        assert isinstance(entry["node_name"], str)
        assert entry["department_id"] == "warehouse"
        assert isinstance(entry["input_state"], dict)
        assert isinstance(entry["output_state"], dict)
        assert isinstance(entry["timestamp"], str) and "T" in entry["timestamp"]
