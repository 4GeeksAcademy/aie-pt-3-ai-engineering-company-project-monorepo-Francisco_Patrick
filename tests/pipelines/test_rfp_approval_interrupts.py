"""Unit and integration tests for User Stories 1 & 2: Scoped Human Approval Interrupts, Parallel Branch Independence, and Explicit Resume Validation (T009, T010, T014, T015)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from data.pipelines.rfp_intake.rfp_approval_service import RFPApprovalService
from presentation.schemas.rfp import ResumeDecisionRequest
from data.pipelines.rfp_approval_completion.pipeline import (
    BranchNotInterruptedError,
    RFPApprovalCompletionPipeline,
    ResumeValidationError,
    validate_resume_decision,
)
from data.pipelines.rfp_approval_completion.state import (
    SqliteSaver,
    format_branch_thread_id,
    format_ticket_thread_id,
    make_branch_config,
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


def _seed_multi_department_ticket(
    repo: SQLModelIntakeTicketRepository,
    departments: list[str] | None = None,
) -> UUID:
    """Seed a ticket that completed Part 1 & Part 2 with evaluated drafts ready for Part 3 approval."""
    ticket_id = uuid4()
    active_depts = departments or ["warehouse", "lastmile"]

    ticket = IntakeTicket.create(
        raw_pdf_path="data/raw/trackflow-request-1.pdf",
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=4096,
        ticket_id=ticket_id,
    )
    ticket.mark_under_evaluation()
    repo.save_ticket(ticket)

    meta = RFPMetadata(
        id=uuid4(),
        ticket_id=ticket_id,
        client_name="ModaViva, S.L.",
        client_country="ES",
        currency="EUR",
        services_requested=["warehousing", "lastmile"],
        monthly_volume=3000,
        deadline="2026-12-20",
        budget_range="25,000 EUR/mes",
        departments_needed=active_depts,  # type: ignore[arg-type]
        unsupported_services=[],
        readability_scores=ReadabilityScores(
            flesch_reading_ease=64.0,
            flesch_kincaid_grade=8.1,
            reading_level_label="Standard",
            word_count=420,
            sentence_count=24,
        ),
    )
    repo.save_metadata(meta)

    lead_map = {
        "warehouse": ("Warehouse Operations", "Ana Whitfield"),
        "lastmile": ("Last Mile and Carrier Management", "Carlos Vega"),
        "reverse": ("Reverse Logistics", "Sofía Ramos"),
    }

    for dept_id in active_depts:
        d_name, d_lead = lead_map[dept_id]
        repo.save_department_section(
            DepartmentSection(
                id=uuid4(),
                ticket_id=ticket_id,
                department_id=dept_id,  # type: ignore[arg-type]
                department_name=d_name,
                responsible_person=d_lead,
                key_aspects={"monthly_volume": 3000, "warehouse_location_preference": "Zaragoza"},
                open_questions=[],
                policy_warnings=[],
                draft_content=(
                    f"## {d_name} Proposal for ModaViva, S.L.\n"
                    f"Lead: {d_lead}. All rates in EUR. We commit to a 90% on-time SLA. "
                    "Turnaround is 48 to 72 hours.\n"
                    "| Monthly Volume Tier | Volume Discount (%) |\n|---|---|\n| 1-2500 | 0% |\n| 2501+ | 5% |"
                ),
                iteration=1,
                status="passed",
                approval_status="pending",
            )
        )

    return ticket_id


def test_scoped_interrupts_and_parallel_branch_independence(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T009 [US1]: Verify both branches enter scoped interrupts and approving lastmile does not block or unpause warehouse."""
    ticket_id = _seed_multi_department_ticket(rfp_repository, ["warehouse", "lastmile"])
    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )

    milestone_info = service.enter_approval_milestone(ticket_id)
    assert milestone_info["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value
    assert milestone_info["branch_statuses"]["warehouse"] == "interrupted"
    assert milestone_info["branch_statuses"]["lastmile"] == "interrupted"

    # Both branches are paused at human_approval_checkpoint interrupt
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is True
    assert service.pipeline.is_branch_interrupted(ticket_id, "lastmile") is True

    # Carlos Vega approves lastmile while Ana Whitfield has NOT reviewed warehouse
    resume_result = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="lastmile",
        decision="approve",
        approver="Carlos Vega",
    )

    assert resume_result["department_id"] == "lastmile"
    assert resume_result["approval_status"] == "approved"
    assert resume_result["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value
    assert resume_result["approved_at"] is not None
    assert resume_result["final_document"] is None

    # Verify lastmile branch completed while warehouse branch remains paused in its interrupt
    assert service.pipeline.is_branch_interrupted(ticket_id, "lastmile") is False
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is True

    # Verify database records reflect independent branch states
    lm_sec = rfp_repository.get_department_section(ticket_id, "lastmile")
    wh_sec = rfp_repository.get_department_section(ticket_id, "warehouse")
    ticket = rfp_repository.get_ticket(ticket_id)

    assert lm_sec is not None and lm_sec.approval_status == "approved"
    assert lm_sec.approver == "Carlos Vega"
    assert lm_sec.approved_at is not None

    assert wh_sec is not None and wh_sec.approval_status == "pending"
    assert wh_sec.approver is None
    assert wh_sec.approved_at is None

    assert ticket is not None and ticket.status == TicketStatus.WAITING_FOR_APPROVAL
    assert rfp_repository.get_final_document(ticket_id) is None


def test_checkpointer_thread_namespacing_and_persistence(
    rfp_repository: SQLModelIntakeTicketRepository,
    tmp_path: Path,
) -> None:
    """T010 [US1]: Verify deterministic thread ID namespacing (`rfp-{ticket_id}:{department}`) and SQLite durability across checkpointer instances."""
    ticket_a = _seed_multi_department_ticket(rfp_repository, ["warehouse", "reverse"])
    ticket_b = _seed_multi_department_ticket(rfp_repository, ["warehouse", "lastmile"])

    assert format_ticket_thread_id(ticket_a) == f"rfp-{ticket_a}"
    assert format_branch_thread_id(ticket_a, "warehouse") == f"rfp-{ticket_a}:warehouse"
    assert format_branch_thread_id(ticket_a, "reverse") == f"rfp-{ticket_a}:reverse"
    assert format_branch_thread_id(ticket_b, "warehouse") == f"rfp-{ticket_b}:warehouse"

    db_file = tmp_path / "durable_checkpoints.sqlite"
    saver_instance_1 = SqliteSaver(db_path=db_file)

    pipeline_1 = RFPApprovalCompletionPipeline(
        repository=rfp_repository,
        checkpointer=saver_instance_1,
    )
    pipeline_1.start_approval_phase(ticket_a)
    pipeline_1.start_approval_phase(ticket_b)

    # Approve ticket_a's warehouse branch on instance 1
    pipeline_1.resume_department_approval(
        ticket_id=ticket_a,
        department_id="warehouse",
        decision="approve",
        approver="Ana Whitfield",
    )

    # Re-instantiate a fresh SqliteSaver and pipeline pointing to the same SQLite file
    saver_instance_2 = SqliteSaver(db_path=db_file)
    pipeline_2 = RFPApprovalCompletionPipeline(
        repository=rfp_repository,
        checkpointer=saver_instance_2,
    )

    # Ticket A warehouse is approved (not interrupted), Ticket A reverse is still interrupted
    assert pipeline_2.is_branch_interrupted(ticket_a, "warehouse") is False
    assert pipeline_2.is_branch_interrupted(ticket_a, "reverse") is True
    # Ticket B warehouse was never touched by Ticket A's approval!
    assert pipeline_2.is_branch_interrupted(ticket_b, "warehouse") is True
    snap_b_wh = pipeline_2.get_branch_snapshot(ticket_b, "warehouse")
    assert snap_b_wh.values["approval_status"] == "pending"


def test_resume_input_validation_and_decision_routing(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T014 [US2]: Verify contract validation for resume payloads and HTTP 409 conflict on already-approved branches."""
    # Invalid department_id
    with pytest.raises(ResumeValidationError, match="Invalid department_id"):
        validate_resume_decision(
            {"department_id": "finance", "decision": "approve", "approver": "Ana Whitfield"}
        )

    # Invalid decision enum
    with pytest.raises(ResumeValidationError, match="Invalid decision"):
        validate_resume_decision(
            {"department_id": "warehouse", "decision": "maybe", "approver": "Ana Whitfield"}
        )

    # Missing approver
    with pytest.raises(ResumeValidationError, match="approver"):
        validate_resume_decision(
            {"department_id": "warehouse", "decision": "approve", "approver": ""}
        )

    # Missing feedback on request_changes
    with pytest.raises(ResumeValidationError, match="feedback"):
        validate_resume_decision(
            {
                "department_id": "warehouse",
                "decision": "request_changes",
                "approver": "Ana Whitfield",
                "feedback": "   ",
            }
        )

    # Missing feedback on reject raises ResumeValidationError
    with pytest.raises(ResumeValidationError, match="feedback"):
        validate_resume_decision(
            {
                "department_id": "warehouse",
                "decision": "reject",
                "approver": "Ana Whitfield",
                "feedback": "   ",
            }
        )

    # Valid reject with non-empty feedback succeeds
    valid_reject = validate_resume_decision(
        {
            "department_id": "warehouse",
            "decision": "reject",
            "approver": "Ana Whitfield",
            "feedback": "Rates exceed allocated departmental budget.",
        }
    )
    assert valid_reject["decision"] == "reject"
    assert valid_reject["feedback"] == "Rates exceed allocated departmental budget."

    # ResumeDecisionRequest schema validation requires feedback on reject
    with pytest.raises(ValueError, match="feedback"):
        ResumeDecisionRequest(
            department_id="warehouse",
            decision="reject",
            approver="Ana Whitfield",
            feedback="",
        )

    ticket_id = _seed_multi_department_ticket(rfp_repository, ["warehouse", "lastmile"])
    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )
    service.enter_approval_milestone(ticket_id)

    # Valid approval succeeds
    res = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="approve",
        approver="Ana Whitfield",
    )
    assert res["approval_status"] == "approved"

    # Duplicate resume on already-approved branch raises BranchNotInterruptedError (HTTP 409)
    with pytest.raises(BranchNotInterruptedError):
        service.resume_department_approval(
            ticket_id=ticket_id,
            department_id="warehouse",
            decision="approve",
            approver="Ana Whitfield",
        )


def test_resume_request_changes_revises_branch_without_rerunning_upstream(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T015 [US2]: Verify resuming with `request_changes` via Command(resume=...) routes to revision node, increments iteration_count, and re-pauses without losing Part 1/2 metadata."""
    ticket_id = _seed_multi_department_ticket(rfp_repository, ["warehouse", "lastmile"])
    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )
    service.enter_approval_milestone(ticket_id)

    original_meta = rfp_repository.get_metadata(ticket_id)
    assert original_meta is not None

    # Ana Whitfield requests changes on warehouse
    change_res = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="request_changes",
        approver="Ana Whitfield",
        feedback="Include explicit Zaragoza pallet racking buffer details.",
    )

    assert change_res["approval_status"] == "changes_requested"
    assert change_res["iteration_count"] == 1
    assert change_res["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value

    # Warehouse branch revised its draft and re-entered the interrupt checkpoint for re-review
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is True

    wh_sec = rfp_repository.get_department_section(ticket_id, "warehouse")
    assert wh_sec is not None
    assert wh_sec.approval_status == "changes_requested"
    assert wh_sec.iteration == 1
    assert wh_sec.review_feedback == "Include explicit Zaragoza pallet racking buffer details."
    assert wh_sec.draft_content is not None

    # Now Ana Whitfield approves the revised draft on the next resume cycle
    approve_res = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="approve",
        approver="Ana Whitfield",
    )
    assert approve_res["approval_status"] == "approved"
    assert service.pipeline.is_branch_interrupted(ticket_id, "warehouse") is False

    # Verify Part 1 metadata and raw_pdf_path were never lost or mutated
    after_meta = rfp_repository.get_metadata(ticket_id)
    ticket = rfp_repository.get_ticket(ticket_id)
    assert after_meta is not None
    assert after_meta.client_name == original_meta.client_name
    assert after_meta.readability_scores == original_meta.readability_scores
    assert ticket is not None and ticket.raw_pdf_path == "data/raw/trackflow-request-1.pdf"


def test_enter_approval_milestone_defaults_to_initial_arbitration(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """Verify that enter_approval_milestone defaults to run_initial_arbitration=True and resolves conflicts on entry."""
    ticket_id = uuid4()
    ticket = IntakeTicket.create(
        raw_pdf_path="data/raw/trackflow-request-1.pdf",
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=4096,
        ticket_id=ticket_id,
    )
    ticket.mark_under_evaluation()
    rfp_repository.save_ticket(ticket)

    meta = RFPMetadata(
        id=uuid4(),
        ticket_id=ticket_id,
        client_name="ModaViva, S.L.",
        client_country="ES",
        currency="EUR",
        services_requested=["warehousing", "lastmile"],
        monthly_volume=5000,
        deadline="2026-12-20",
        budget_range="25,000 EUR/mes",
        departments_needed=["warehouse", "lastmile"],  # type: ignore[arg-type]
        unsupported_services=[],
        readability_scores=ReadabilityScores(
            flesch_reading_ease=64.0,
            flesch_kincaid_grade=8.1,
            reading_level_label="Standard",
            word_count=420,
            sentence_count=24,
        ),
    )
    rfp_repository.save_metadata(meta)

    rfp_repository.save_department_section(
        DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="warehouse",  # type: ignore[arg-type]
            department_name="Warehouse Operations",
            responsible_person="Ana Whitfield",
            key_aspects={"warehouse_capacity": 3000},
            open_questions=[],
            policy_warnings=[],
            draft_content="Committed capacity: 3,000 orders per month at Zaragoza hub. Rates in EUR.",
            iteration=0,
            status="passed",
            approval_status="pending",
        )
    )

    rfp_repository.save_department_section(
        DepartmentSection(
            id=uuid4(),
            ticket_id=ticket_id,
            department_id="lastmile",  # type: ignore[arg-type]
            department_name="Last Mile and Carrier Management",
            responsible_person="Carlos Vega",
            key_aspects={"monthly_volume": 5000},
            open_questions=[],
            policy_warnings=[],
            draft_content="We handle 5,000 monthly shipments across Spain. Rates in EUR.",
            iteration=0,
            status="passed",
            approval_status="pending",
        )
    )

    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )

    # Calling without run_initial_arbitration argument should default to True
    milestone_res = service.enter_approval_milestone(ticket_id)
    assert milestone_res["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value

    # Verify arbitration log was created by initial arbitration
    logs = service.list_arbitration_logs(ticket_id)
    vol_logs = [log for log in logs if log.trigger_id == "volume-vs-capacity"]
    assert len(vol_logs) == 1
    assert vol_logs[0].resolution_details["capped_volume"] == 3000

    # Verify lastmile section draft was adjusted by initial arbitration prior to human review
    lm_sec = rfp_repository.get_department_section(ticket_id, "lastmile")
    assert lm_sec is not None
    assert lm_sec.approval_status == "pending"
    assert "3000" in lm_sec.draft_content
    assert "Miguel Torres" in lm_sec.draft_content
    assert "capped at 3000" in lm_sec.draft_content


def test_rejection_lifecycle_and_commercial_reopening(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """Verify that department rejection escalates ticket out of esperando_aprobación and allows commercial reopening."""
    ticket_id = _seed_multi_department_ticket(rfp_repository, ["warehouse", "lastmile"])
    service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )
    service.enter_approval_milestone(ticket_id)

    # 1. Department rejects proposal
    reject_res = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="reject",
        approver="Ana Whitfield",
        feedback="Rechazado por falta de viabilidad en capacidad de almacenamiento.",
    )
    assert reject_res["approval_status"] == "rejected"
    assert reject_res["ticket_status"] == TicketStatus.NEEDS_HUMAN_REVIEW.value
    assert reject_res["ticket_status"] != TicketStatus.WAITING_FOR_APPROVAL.value

    # Verify repository ticket was escalated to needs_human_review
    saved_ticket = rfp_repository.get_ticket(ticket_id)
    assert saved_ticket is not None
    assert saved_ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW

    # 2. Blind repeat resume without reopening fails with BranchNotInterruptedError
    with pytest.raises(BranchNotInterruptedError):
        service.resume_department_approval(
            ticket_id=ticket_id,
            department_id="warehouse",
            decision="reject",
            approver="Ana Whitfield",
            feedback="Rechazado de nuevo.",
        )

    # 3. Commercial reopening with request_changes allows remediation
    reopen_res = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="request_changes",
        approver="Miguel Torres",
        feedback="Ajustar viabilidad comercial y replantear layout de estanterías.",
    )
    assert reopen_res["approval_status"] == "changes_requested"
    assert reopen_res["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value

    reopened_ticket = rfp_repository.get_ticket(ticket_id)
    assert reopened_ticket is not None
    assert reopened_ticket.status == TicketStatus.WAITING_FOR_APPROVAL

    # 4. Warehouse lead approves remediated draft
    approve_wh = service.resume_department_approval(
        ticket_id=ticket_id,
        department_id="warehouse",
        decision="approve",
        approver="Ana Whitfield",
    )
    assert approve_wh["approval_status"] == "approved"


