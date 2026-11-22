"""Automated continuous End-to-End Integration Test driving Parts 1, 2, and 3 (T043 - User Story 6).

Verifies seamless handoffs from:
- Part 1: PDF / Markdown Intake, Readability Scoring, Classification, Orchestrator Metadata Extraction,
  Department Worker Key-Aspects Analysis, and Part 1 Handoff Synthesis (`analisis_completo`).
- Part 2: Department Proposal Drafting, Parallel 3-Dimensional Evaluation (Readability, Relevance, Compliance),
  and Part 3 Handoff Compilation (`en_evaluación`).
- Part 3: Scoped Department Approval Interrupts (`esperando_aprobación`), Independent Branch Resumption,
  Deterministic Conflict Arbitration, and Automatic Final Document Synthesis (`terminado`).
"""

from __future__ import annotations

from uuid import uuid4

from application.agent.rfp_approval_service import RFPApprovalService
from application.agent.rfp_intake_pipeline import RFPIntakePipeline
from application.agent.rfp_response_service import RFPResponseGenerationService
from data.pipelines.rfp_approval_completion.state import SqliteSaver
from domain.rfp.entities import IntakeTicket, TicketStatus
from infrastructure.persistence.sqlmodel.rfp_repository import (
    SQLModelIntakeTicketRepository,
)

SAMPLE_MODAVIVA_RFP_MARKDOWN = """# Solicitud de Propuesta (RFP) — ModaViva, S.L.

**Cliente**: ModaViva, S.L.
**País de Operación**: España (ES)
**Moneda**: EUR
**Volumen Mensual Estimado**: 3,500 pedidos mensuales
**Fecha Límite**: 2026-12-15

## 1. Alcance de Servicios Solicitados
ModaViva solicita propuesta logística integral para nuestras operaciones de e-commerce de moda en España:
1. **Operaciones de Almacén (Warehousing)**:
   - Centro logístico preferido en Zaragoza con almacenamiento de aproximadamente 300 SKUs textiles.
   - Preparación de pedidos (pick & pack) y control de inventario.
2. **Transporte y Última Milla (Last Mile)**:
   - Distribución nacional en España peninsular para 3,500 envíos mensuales con seguimiento completo.
3. **Logística Inversa y Devoluciones (Reverse Logistics)**:
   - Gestión de ventana de devoluciones de 30 días, tasa estimada del 15%, con inspección de calidad de prendas.
"""


def test_continuous_e2e_pipeline_parts_1_2_and_3(
    rfp_repository: SQLModelIntakeTicketRepository,
    sqlite_checkpointer: SqliteSaver,
) -> None:
    """T043 [US6]: Drive an RFP ticket continuously through Part 1 -> Part 2 -> Part 3 with zero state skips or data loss."""
    ticket_id = uuid4()
    raw_pdf_path = "data/raw/trackflow-request-1.pdf"

    # -------------------------------------------------------------------------
    # STEP 1: Part 1 — RFP Intake & Multi-Department Analysis
    # -------------------------------------------------------------------------
    ticket = IntakeTicket.create(
        raw_pdf_path=raw_pdf_path,
        raw_pdf_filename="trackflow-request-1.pdf",
        file_size_bytes=8192,
        ticket_id=ticket_id,
    )
    rfp_repository.save_ticket(ticket)
    assert ticket.status == TicketStatus.ANALIZANDO

    intake_pipeline = RFPIntakePipeline(repository=rfp_repository)
    # Stub converter to return deterministic ModaViva RFP markdown without requiring external PDF binary
    intake_pipeline.converter.convert_to_markdown = lambda _path: SAMPLE_MODAVIVA_RFP_MARKDOWN  # type: ignore[method-assign]

    part1_state = intake_pipeline.execute(ticket_id, raw_pdf_path)
    assert part1_state["is_rfp"] is True
    assert part1_state["status"] == TicketStatus.ANALISIS_COMPLETO.value

    ticket_after_p1 = rfp_repository.get_ticket(ticket_id)
    meta_after_p1 = rfp_repository.get_metadata(ticket_id)
    handoff_p1 = rfp_repository.get_handoff_payload(ticket_id)
    sections_after_p1 = rfp_repository.list_department_sections(ticket_id)

    assert ticket_after_p1 is not None
    assert ticket_after_p1.status == TicketStatus.ANALISIS_COMPLETO
    assert meta_after_p1 is not None
    assert meta_after_p1.client_country == "ES"
    assert meta_after_p1.currency == "EUR"
    assert handoff_p1 is not None
    assert len(sections_after_p1) >= 2

    active_depts = list(meta_after_p1.departments_needed)
    assert len(active_depts) >= 2

    # -------------------------------------------------------------------------
    # STEP 2: Part 2 — Department Proposal Generation & Parallel 3D Evaluation
    # -------------------------------------------------------------------------
    part2_service = RFPResponseGenerationService(repository=rfp_repository)
    initiated_ticket, queued_depts = part2_service.initiate_proposal_generation(ticket_id)
    assert initiated_ticket.status == TicketStatus.DRAFTING
    assert queued_depts == active_depts

    part3_handoff = part2_service.execute_pipeline(ticket_id)
    assert part3_handoff.overall_status == "passed"
    assert set(part3_handoff.department_sections.keys()) == set(active_depts)

    ticket_after_p2 = rfp_repository.get_ticket(ticket_id)
    assert ticket_after_p2 is not None
    assert ticket_after_p2.status == TicketStatus.UNDER_EVALUATION

    for dept_id in active_depts:
        sec_p2 = rfp_repository.get_department_section(ticket_id, dept_id)
        assert sec_p2 is not None
        assert sec_p2.status == "passed"
        assert sec_p2.draft_content is not None and len(sec_p2.draft_content) > 50
        assert len(sec_p2.evaluation_results) >= 1
        assert sec_p2.evaluation_results[-1]["overall_pass"] is True

    # -------------------------------------------------------------------------
    # STEP 3: Part 3 — Scoped Department Approvals, Arbitration & Final Synthesis
    # -------------------------------------------------------------------------
    part3_service = RFPApprovalService(
        repository=rfp_repository,
        checkpointer=sqlite_checkpointer,
    )
    milestone = part3_service.enter_approval_milestone(
        ticket_id=ticket_id,
        run_initial_arbitration=True,
    )
    assert milestone["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value

    ticket_in_p3 = rfp_repository.get_ticket(ticket_id)
    assert ticket_in_p3 is not None
    assert ticket_in_p3.status == TicketStatus.WAITING_FOR_APPROVAL

    # Verify all active departments are paused in independent scoped interrupts
    for dept_id in active_depts:
        assert part3_service.pipeline.is_branch_interrupted(ticket_id, dept_id) is True

    lead_approvers = {
        "warehouse": "Ana Whitfield",
        "lastmile": "Carlos Vega",
        "reverse": "Sofía Ramos",
    }

    # Approve each department one by one; verify synthesis only triggers on the final one
    for idx, dept_id in enumerate(active_depts):
        is_last = idx == len(active_depts) - 1
        res = part3_service.resume_department_approval(
            ticket_id=ticket_id,
            department_id=dept_id,
            decision="approve",
            approver=lead_approvers[dept_id],
        )
        assert res["approval_status"] == "approved"

        if not is_last:
            assert res["ticket_status"] == TicketStatus.WAITING_FOR_APPROVAL.value
            assert res["final_document"] is None
            # Remaining branches are still paused in their interrupts
            remaining_dept = active_depts[idx + 1]
            assert (
                part3_service.pipeline.is_branch_interrupted(ticket_id, remaining_dept)
                is True
            )
        else:
            assert res["ticket_status"] == TicketStatus.TERMINADO.value
            assert res["final_document"] is not None

    # -------------------------------------------------------------------------
    # STEP 4: Final State & Data Integrity Verification Across Parts 1, 2, 3
    # -------------------------------------------------------------------------
    final_ticket = rfp_repository.get_ticket(ticket_id)
    final_meta = rfp_repository.get_metadata(ticket_id)
    final_doc = rfp_repository.get_final_document(ticket_id)

    assert final_ticket is not None
    assert final_ticket.status == TicketStatus.TERMINADO
    assert final_ticket.raw_pdf_path == raw_pdf_path
    assert final_ticket.file_size_bytes == 8192

    assert final_meta is not None
    assert final_meta.client_name == meta_after_p1.client_name
    assert final_meta.currency == "EUR"
    assert final_meta.readability_scores == meta_after_p1.readability_scores

    assert final_doc is not None
    assert final_doc.ticket_id == ticket_id
    assert final_doc.currency == "EUR"
    assert set(final_doc.sections.keys()) == set(active_depts)
    for dept_id in active_depts:
        assert final_doc.sections[dept_id]["responsible_person"] == lead_approvers[dept_id]
        assert len(final_doc.sections[dept_id]["approved_content"]) > 50
