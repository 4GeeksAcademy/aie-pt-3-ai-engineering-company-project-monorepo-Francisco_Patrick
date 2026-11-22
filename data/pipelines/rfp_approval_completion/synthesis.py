"""Automatic Final Document Synthesis & Currency Binding (Part 3 of 3).

Consolidates all approved department sections into a client-ready `FinalDocument` once and
only once 100% of active departments have recorded `approval_status == "approved"`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import UUID, uuid4

from data.pipelines.rfp_approval_completion.arbitration import resolve_canonical_currency
from data.pipelines.rfp_approval_completion.state import (
    COMMERCIAL_DIRECTOR,
    DEPARTMENT_LEADS,
    traced_node,
)
from domain.rfp.entities import FinalDocument, TicketStatus


def can_synthesize_final_document(
    active_departments: Sequence[str],
    department_sections: Dict[str, Dict[str, Any]],
) -> bool:
    """Return True if and only if every active department section has recorded 'approved' status."""
    if not active_departments:
        return False
    for dept_id in active_departments:
        sec = department_sections.get(dept_id)
        if not sec:
            return False
        if sec.get("approval_status") != "approved":
            return False
    return True


def synthesize_final_document(
    ticket_id: Union[UUID, str],
    rfp_metadata: Dict[str, Any],
    department_sections: Dict[str, Dict[str, Any]],
    active_departments: Optional[Sequence[str]] = None,
    document_id: Optional[UUID] = None,
) -> FinalDocument:
    """Compile the consolidated FinalDocument from 100% approved department sections.

    Raises:
        ValueError: If any active department is missing or not in 'approved' status.
    """
    tid = ticket_id if isinstance(ticket_id, UUID) else UUID(str(ticket_id))
    meta = dict(rfp_metadata or {})
    depts: List[str] = list(
        active_departments
        or meta.get("departments_needed")
        or list(department_sections.keys())
    )

    if not can_synthesize_final_document(depts, department_sections):
        unapproved = [
            d
            for d in depts
            if department_sections.get(d, {}).get("approval_status") != "approved"
        ]
        raise ValueError(
            f"Cannot synthesize FinalDocument for ticket '{tid}': "
            f"active department(s) not yet approved: {unapproved}"
        )

    client_name = str(meta.get("client_name") or "Prospective Client")
    client_country = str(meta.get("client_country") or "ES").upper()
    currency = resolve_canonical_currency(client_country)
    monthly_volume = meta.get("monthly_volume")
    deadline = meta.get("deadline")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    title = (
        f"TrackFlow Integrated Logistics Proposal — {client_name}"
        if client_country == "US"
        else f"Propuesta Logística Integral TrackFlow — {client_name}"
    )

    compiled_sections: Dict[str, Any] = {}
    lead_signoffs: List[str] = []

    for dept_id in depts:
        sec = department_sections[dept_id]
        default_name, default_lead = DEPARTMENT_LEADS.get(
            dept_id,  # type: ignore[arg-type]
            (dept_id.capitalize(), "Department Lead"),
        )
        dept_name = str(sec.get("department_name") or default_name)
        lead_name = str(sec.get("approver") or sec.get("responsible_person") or default_lead)
        approved_content = str(sec.get("draft_content") or "")
        approved_at_raw = sec.get("approved_at")
        if isinstance(approved_at_raw, datetime):
            approved_at_str = approved_at_raw.isoformat()
        elif isinstance(approved_at_raw, str) and approved_at_raw.strip():
            approved_at_str = approved_at_raw
        else:
            approved_at_str = now_iso

        compiled_sections[dept_id] = {
            "department_name": dept_name,
            "responsible_person": lead_name,
            "approved_content": approved_content,
            "approved_at": approved_at_str,
        }
        lead_signoffs.append(f"{dept_name} ({lead_name})")

    volume_clause = (
        f"supporting an estimated monthly volume of {monthly_volume:,} orders"
        if isinstance(monthly_volume, int)
        else "tailored to the client's projected monthly order volume"
    )
    deadline_clause = f" Target launch / response deadline: {deadline}." if deadline else ""

    executive_summary = (
        f"Executive Commercial Proposal prepared for {client_name} ({client_country}), "
        f"bound exclusively in {currency} ({volume_clause}).{deadline_clause} "
        f"All active operational departments — {', '.join(lead_signoffs)} — have completed "
        f"technical compliance evaluation and formal Human-in-the-Loop sign-off under "
        f"Commercial Director {COMMERCIAL_DIRECTOR}."
    )

    return FinalDocument(
        id=document_id or uuid4(),
        ticket_id=tid,
        title=title,
        client_name=client_name,
        currency=currency,
        executive_summary=executive_summary,
        sections=compiled_sections,
        generated_at=now,
    )


@traced_node("final_synthesis_node")
def final_synthesis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph final synthesis node invoked automatically when 100% of active departments approve."""
    raw_tid = state.get("ticket_id")
    tid = UUID(str(raw_tid)) if raw_tid else uuid4()
    meta = dict(state.get("rfp_metadata") or {})
    sections = dict(state.get("department_sections") or {})
    active_depts = list(
        state.get("active_departments")
        or meta.get("departments_needed")
        or list(sections.keys())
    )

    if not can_synthesize_final_document(active_depts, sections):
        return {
            "ticket_status": TicketStatus.WAITING_FOR_APPROVAL.value,
            "final_document": None,
        }

    final_doc = synthesize_final_document(
        ticket_id=tid,
        rfp_metadata=meta,
        department_sections=sections,
        active_departments=active_depts,
    )

    return {
        "final_document": final_doc.to_schema_dict(),
        "ticket_status": TicketStatus.TERMINADO.value,
    }
