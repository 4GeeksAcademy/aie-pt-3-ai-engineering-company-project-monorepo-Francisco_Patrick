"""Unit tests for User Story 3: Deterministic Conflict Arbitration & Revision Iteration Caps (T019, T020, T021, T022)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import jsonschema
from sqlmodel import Session

from data.pipelines.rfp_intake.rfp_approval_service import RFPApprovalService
from data.pipelines.rfp_intake.rfp_arbitration_agent import RFPArbitrationAgent
from data.pipelines.rfp_approval_completion.arbitration import (
    arbitration_node,
    evaluate_and_arbitrate_conflicts,
)
from data.pipelines.rfp_approval_completion.state import (
    COMMERCIAL_DIRECTOR,
    REVERSE_LOGISTICS_LEAD,
    SqliteSaver,
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
ARBITRATION_SCHEMA_PATH = (
    REPO_ROOT
    / "specs"
    / "033-rfp-approval-completion"
    / "contracts"
    / "arbitration-log.schema.json"
)


def _load_arbitration_schema() -> dict:
    with open(ARBITRATION_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_volume_vs_capacity_conflict_arbitration_under_miguel_torres(
    rfp_repository: SQLModelIntakeTicketRepository,
) -> None:
    """T019 [US3]: Verify `volume-vs-capacity` caps proposal volume at warehouse capacity under arbiter Miguel Torres."""
    ticket_id = uuid4()
    ticket = IntakeTicket.create(
        raw_pdf_path="data/raw/trackflow-request-1.pdf",
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=2048,
        ticket_id=ticket_id,
    )
    rfp_repository.save_ticket(ticket)

    rfp_metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "ES",
        "currency": "EUR",
        "monthly_volume": 5000,
        "departments_needed": ["warehouse", "lastmile"],
    }
    department_sections = {
        "warehouse": {
            "department_id": "warehouse",
            "department_name": "Warehouse Operations",
            "responsible_person": "Ana Whitfield",
            "key_aspects": {"warehouse_capacity": 3000},
            "draft_content": (
                "## Warehouse Proposal\n"
                "Committed capacity: 3,000 orders per month at Zaragoza hub. "
                "Rates in EUR: 16.00 EUR por m³. 90% on-time SLA."
            ),
            "iteration_count": 0,
            "approval_status": "pending",
        },
        "lastmile": {
            "department_id": "lastmile",
            "department_name": "Last Mile and Carrier Management",
            "responsible_person": "Carlos Vega",
            "key_aspects": {"monthly_volume": 5000},
            "draft_content": (
                "## Last Mile Proposal\n"
                "We handle 5,000 monthly shipments across Spain. "
                "Rates in EUR: 5.20 EUR per parcel. 98.5% on-time SLA."
            ),
            "iteration_count": 0,
            "approval_status": "pending",
        },
    }

    agent = RFPArbitrationAgent(repository=rfp_repository)
    updated_meta, updated_sections, logs = agent.evaluate_and_resolve(
        ticket_id=ticket_id,
        rfp_metadata=rfp_metadata,
        department_sections=department_sections,
    )

    vol_logs = [log for log in logs if log.trigger_id == "volume-vs-capacity"]
    assert len(vol_logs) == 1
    vlog = vol_logs[0]

    assert vlog.arbiter == COMMERCIAL_DIRECTOR
    assert vlog.resolution_details["capped_volume"] == 3000
    assert "lastmile" in vlog.resolution_details["affected_departments"]
    assert updated_meta["monthly_volume"] == 3000
    assert updated_sections["lastmile"]["key_aspects"]["monthly_volume"] == 3000
    assert updated_sections["lastmile"]["approval_status"] == "changes_requested"
    assert "3000" in updated_sections["lastmile"]["draft_content"]

    # Validate against JSON Schema contract
    schema = _load_arbitration_schema()
    jsonschema.validate(instance=vlog.to_schema_dict(), schema=schema)

    # Verify DB persistence
    persisted_logs = rfp_repository.list_arbitration_logs(ticket_id)
    assert any(p.trigger_id == "volume-vs-capacity" for p in persisted_logs)


def test_returns_sla_breach_conflict_arbitration_under_sofia_ramos(
    rfp_repository: SQLModelIntakeTicketRepository,
) -> None:
    """T020 [US3]: Verify `returns-sla-breach` triggers when <48h return turnaround is promised, assigning Sofía Ramos and forcing changes_requested."""
    ticket_id = uuid4()
    ticket = IntakeTicket.create(
        raw_pdf_path="data/raw/trackflow-request-1.pdf",
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=2048,
        ticket_id=ticket_id,
    )
    rfp_repository.save_ticket(ticket)

    rfp_metadata = {
        "client_name": "ModaViva, S.L.",
        "client_country": "ES",
        "currency": "EUR",
        "monthly_volume": 2500,
        "departments_needed": ["reverse"],
    }
    department_sections = {
        "reverse": {
            "department_id": "reverse",
            "department_name": "Reverse Logistics",
            "responsible_person": "Sofía Ramos",
            "key_aspects": {"return_window_days": 30},
            "draft_content": (
                "## Reverse Logistics Proposal\n"
                "We offer same-day return inspection with a 24 hours return turnaround in EUR (2.40 EUR)."
            ),
            "iteration_count": 0,
            "approval_status": "approved",
        }
    }

    _, updated_sections, logs = evaluate_and_arbitrate_conflicts(
        ticket_id=ticket_id,
        rfp_metadata=rfp_metadata,
        department_sections=department_sections,
    )

    sla_logs = [log for log in logs if log.trigger_id == "returns-sla-breach"]
    assert len(sla_logs) == 1
    slog = sla_logs[0]

    assert slog.arbiter == REVERSE_LOGISTICS_LEAD
    assert "reverse" in slog.resolution_details["affected_departments"]
    assert updated_sections["reverse"]["approval_status"] == "changes_requested"
    assert updated_sections["reverse"]["iteration_count"] == 1

    schema = _load_arbitration_schema()
    jsonschema.validate(instance=slog.to_schema_dict(), schema=schema)


def test_currency_mismatch_conflict_arbitration_and_canonical_rewriting() -> None:
    """T021 [US3]: Verify `currency-mismatch` triggers for US client quoted in EUR and ES client quoted in USD, rewriting to canonical currency under Miguel Torres."""
    ticket_id = uuid4()
    state = {
        "ticket_id": str(ticket_id),
        "rfp_metadata": {
            "client_name": "Luna Cosmetics Inc.",
            "client_country": "US",
            "currency": "EUR",
            "monthly_volume": 4000,
            "departments_needed": ["warehouse"],
        },
        "department_sections": {
            "warehouse": {
                "department_id": "warehouse",
                "department_name": "Warehouse Operations",
                "responsible_person": "Ana Whitfield",
                "key_aspects": {"currency": "EUR"},
                "draft_content": (
                    "## Warehouse Proposal for Luna Cosmetics Inc.\n"
                    "Pallet Storage Rate: 16.00 EUR por m³ (€16.00). "
                    "Turnaround takes 48 to 72 hours."
                ),
                "iteration_count": 0,
                "approval_status": "pending",
            }
        },
        "arbitration_logs": [],
        "execution_trace": [],
    }

    out = arbitration_node(state)
    assert out["rfp_metadata"]["currency"] == "USD"
    wh_draft = out["department_sections"]["warehouse"]["draft_content"]
    assert "USD" in wh_draft
    assert "EUR" not in wh_draft
    assert "€" not in wh_draft

    curr_logs = [
        log for log in out["arbitration_logs"] if log["trigger_id"] == "currency-mismatch"
    ]
    assert len(curr_logs) == 1
    assert curr_logs[0]["arbiter"] == COMMERCIAL_DIRECTOR
    assert curr_logs[0]["resolution_details"]["enforced_currency"] == "USD"

    schema = _load_arbitration_schema()
    jsonschema.validate(instance=curr_logs[0], schema=schema)


def test_revision_iteration_cap_and_commercial_escalation(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T022 [US3]: Verify revision loops enforce a hard cap of 2 revisions (3 total attempts) and escalate to Miguel Torres without discarding the ticket."""
    ticket_id = uuid4()
    ticket = IntakeTicket.create(
        raw_pdf_path="data/raw/trackflow-request-1.pdf",
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=2048,
        ticket_id=ticket_id,
    )
    ticket.mark_under_evaluation()
    rfp_repository.save_ticket(ticket)

    rfp_repository.save_metadata(
        RFPMetadata(
            id=uuid4(),
            ticket_id=ticket_id,
            client_name="ModaViva, S.L.",
            client_country="ES",
            currency="EUR",
            services_requested=["warehousing"],
            monthly_volume=3000,
            deadline="2026-12-20",
            budget_range=None,
            departments_needed=["warehouse"],
            unsupported_services=[],
            readability_scores=ReadabilityScores(65.0, 8.0, "Standard", 300, 18),
        )
    )
    rfp_repository.save_department_section(
        DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="warehouse",
            department_name="Warehouse Operations",
            responsible_person="Ana Whitfield",
            key_aspects={"warehouse_location_preference": "Zaragoza"},
            open_questions=[],
            policy_warnings=[],
            draft_content="## Initial Warehouse Draft (Attempt 1) in EUR",
            iteration=0,
            status="passed",
        )
    )

    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
        max_revisions=2,
    )
    service.enter_approval_milestone(ticket_id)

    # Revision 1 (iteration_count becomes 1)
    r1 = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="request_changes",
        approver="Ana Whitfield",
        feedback="Revision 1: Clarify pallet storage tiers.",
    )
    assert r1["approval_status"] == "changes_requested"
    assert r1["iteration_count"] == 1
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is True

    # Revision 2 (iteration_count becomes 2)
    r2 = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="request_changes",
        approver="Ana Whitfield",
        feedback="Revision 2: Adjust onboarding lead time.",
    )
    assert r2["approval_status"] == "changes_requested"
    assert r2["iteration_count"] == 2
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is True

    # 3rd review cycle: requesting changes again hits max_revisions=2 -> escalates to Miguel Torres!
    r3 = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="request_changes",
        approver="Ana Whitfield",
        feedback="Revision 3: Still unsatisfied with storage terms.",
    )
    assert r3["approval_status"] == "needs_human_review"
    assert r3["ticket_status"] == TicketStatus.NEEDS_HUMAN_REVIEW.value
    assert r3["escalation_note"] is not None
    assert COMMERCIAL_DIRECTOR in r3["escalation_note"]

    # Branch loop has terminated (no longer paused in interrupt)
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is False

    # Ticket in DB is needs_human_review, NEVER descartado
    db_ticket = rfp_repository.get_ticket(ticket_id)
    assert db_ticket is not None
    assert db_ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW
    assert db_ticket.status != TicketStatus.DESCARTADO
