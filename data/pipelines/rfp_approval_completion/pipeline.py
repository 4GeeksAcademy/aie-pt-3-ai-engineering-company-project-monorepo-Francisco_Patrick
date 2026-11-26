"""Part 3 LangGraph Pipeline: Scoped Department Approval Interrupts, Arbitration & Final Synthesis.

Implements:
- Independent per-department approval branch graphs (`warehouse`, `lastmile`, `reverse`) compiled with
  a persistent SQLite/PostgreSQL checkpointer (`SqliteSaver`) namespaced by `rfp-{ticket_id}:{department_id}`.
- Native LangGraph `interrupt()` and `Command(resume=...)` mechanics so approving Department A never
  waits for, blocks, or unpauses Department B.
- Explicit input validation (`validate_resume_decision`) enforcing valid decisions (`approve`, `reject`,
  `request_changes`) and mandatory revision feedback.
- Bounded revision loops (default max 2 revisions / 3 total attempts) with graceful escalation to
  Commercial Director Miguel Torres (`needs_human_review`, never discarding the ticket).
- Deterministic conflict arbitration node (`arbitration_node`) and automatic final proposal synthesis
  (`final_synthesis_node`) transitioning the ticket to `terminado` (`done`) upon 100% department approval.
- Structured execution trace logging across all nodes (`execution_trace`).
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_intake.rfp_generator_agents import (  # noqa: E402
    BaseDepartmentGeneratorAgent,
    get_department_generator_agent,
)
from data.pipelines.rfp_approval_completion.arbitration import (  # noqa: E402
    arbitration_node,
    evaluate_and_arbitrate_conflicts,
)
from data.pipelines.rfp_approval_completion.state import (  # noqa: E402
    COMMERCIAL_DIRECTOR,
    DEPARTMENT_LEADS,
    ApprovalDecisionLiteral,
    DepartmentBranchApprovalState,
    DepartmentIdLiteral,
    ExecutionTraceEntryDict,
    SqliteSaver,
    format_branch_thread_id,
    get_default_checkpointer,
    make_branch_config,
    record_execution_trace,
    traced_node,
)
from data.pipelines.rfp_approval_completion.synthesis import (  # noqa: E402
    can_synthesize_final_document,
    final_synthesis_node,
    synthesize_final_document,
)
from data.pipelines.rfp_response_generation.evaluator import (  # noqa: E402
    DepartmentSectionEvaluator,
)
from domain.rfp.entities import (  # noqa: E402
    ArbitrationLog,
    DepartmentSection,
    FinalDocument,
    TicketStatus,
)
from domain.rfp.ports import IntakeTicketRepositoryPort  # noqa: E402

logger = logging.getLogger("rfp_approval_completion_pipeline")

VALID_DEPARTMENTS: Tuple[DepartmentIdLiteral, ...] = ("warehouse", "lastmile", "reverse")
VALID_DECISIONS: Tuple[ApprovalDecisionLiteral, ...] = ("approve", "reject", "request_changes")
DEFAULT_MAX_REVISIONS = 2  # 2 revisions = 3 total attempts


class ResumeValidationError(ValueError):
    """Raised when a human resume payload fails contract validation (HTTP 422 / 400)."""


class BranchNotInterruptedError(RuntimeError):
    """Raised when attempting to resume a branch that is not paused or is already finalized (HTTP 409)."""


def validate_resume_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate incoming human approval resume payload per resume-decision.schema.json."""
    if not isinstance(payload, dict):
        raise ResumeValidationError("Resume decision payload must be a JSON object.")

    dept_id = payload.get("department_id")
    if dept_id not in VALID_DEPARTMENTS:
        raise ResumeValidationError(
            f"Invalid department_id '{dept_id}'. Must be one of {VALID_DEPARTMENTS}."
        )

    decision = payload.get("decision")
    if decision not in VALID_DECISIONS:
        raise ResumeValidationError(
            f"Invalid decision '{decision}'. Must be one of {VALID_DECISIONS}."
        )

    approver = payload.get("approver")
    if not isinstance(approver, str) or len(approver.strip()) < 2:
        raise ResumeValidationError(
            "Valid 'approver' name (minimum 2 characters) is required."
        )

    feedback = payload.get("feedback")
    if decision in ("request_changes", "reject"):
        if not isinstance(feedback, str) or len(feedback.strip()) < 5:
            raise ResumeValidationError(
                f"Non-empty revision 'feedback' (minimum 5 characters) is mandatory when decision is '{decision}'."
            )

    return {
        "department_id": dept_id,
        "decision": decision,
        "approver": approver.strip(),
        "feedback": feedback.strip() if isinstance(feedback, str) and feedback.strip() else None,
    }


class RFPApprovalCompletionPipeline:
    """Orchestrates Part 3 scoped department approval branches, deterministic arbitration, and final synthesis."""

    def __init__(
        self,
        repository: Optional[IntakeTicketRepositoryPort] = None,
        checkpointer: Optional[SqliteSaver] = None,
        evaluator: Optional[DepartmentSectionEvaluator] = None,
        generators: Optional[Dict[str, BaseDepartmentGeneratorAgent]] = None,
        max_revisions: int = DEFAULT_MAX_REVISIONS,
    ) -> None:
        self.repository = repository
        self.checkpointer = checkpointer or get_default_checkpointer()
        self.evaluator = evaluator or DepartmentSectionEvaluator()
        self.generators: Dict[str, BaseDepartmentGeneratorAgent] = generators or {}
        self.max_revisions = max_revisions
        self.branch_graph = self._build_branch_graph()

    def _get_generator(self, department_id: DepartmentIdLiteral) -> BaseDepartmentGeneratorAgent:
        if department_id in self.generators:
            return self.generators[department_id]
        return get_department_generator_agent(department_id)

    # -------------------------------------------------------------------------
    # Scoped Per-Department Branch Graph
    # -------------------------------------------------------------------------

    def _build_branch_graph(self) -> Any:
        builder = StateGraph(DepartmentBranchApprovalState)

        builder.add_node("prepare_branch_review", self._node_prepare_branch_review)
        builder.add_node("human_approval_checkpoint", self._node_human_approval_checkpoint)
        builder.add_node("finalize_branch_approval", self._node_finalize_branch_approval)
        builder.add_node("finalize_branch_rejection", self._node_finalize_branch_rejection)
        builder.add_node("revise_department_draft", self._node_revise_department_draft)
        builder.add_node("escalate_branch_to_commercial", self._node_escalate_branch_to_commercial)

        builder.add_edge(START, "prepare_branch_review")
        builder.add_edge("prepare_branch_review", "human_approval_checkpoint")

        def route_after_checkpoint(state: DepartmentBranchApprovalState) -> str:
            status = state.get("approval_status", "pending")
            if status == "approved":
                return "finalize_branch_approval"
            if status == "rejected":
                return "finalize_branch_rejection"
            if status == "needs_human_review":
                return "escalate_branch_to_commercial"
            if status == "changes_requested":
                curr_iter = int(state.get("iteration_count", 0))
                max_rev = int(state.get("max_revisions", self.max_revisions))
                if curr_iter >= max_rev:
                    return "escalate_branch_to_commercial"
                return "revise_department_draft"
            return END

        builder.add_conditional_edges(
            "human_approval_checkpoint",
            route_after_checkpoint,
            [
                "finalize_branch_approval",
                "finalize_branch_rejection",
                "revise_department_draft",
                "escalate_branch_to_commercial",
                END,
            ],
        )

        # Revision loop re-enters human_approval_checkpoint (and pauses at interrupt() again)
        builder.add_edge("revise_department_draft", "human_approval_checkpoint")
        builder.add_edge("finalize_branch_approval", END)
        builder.add_edge("finalize_branch_rejection", END)
        builder.add_edge("escalate_branch_to_commercial", END)

        return builder.compile(checkpointer=self.checkpointer)

    @traced_node("prepare_branch_review")
    def _node_prepare_branch_review(
        self, state: DepartmentBranchApprovalState
    ) -> Dict[str, Any]:
        dept_id = state["department_id"]
        default_name, default_lead = DEPARTMENT_LEADS[dept_id]
        return {
            "department_name": state.get("department_name") or default_name,
            "responsible_person": state.get("responsible_person") or default_lead,
            "approval_status": state.get("approval_status") or "pending",
            "iteration_count": int(state.get("iteration_count", 0)),
            "max_revisions": int(state.get("max_revisions", self.max_revisions)),
        }

    def _node_human_approval_checkpoint(
        self, state: DepartmentBranchApprovalState
    ) -> Dict[str, Any]:
        """Pause branch execution via LangGraph `interrupt()` and process resumed human decision."""
        dept_id = state["department_id"]
        interrupt_request = {
            "ticket_id": state["ticket_id"],
            "department_id": dept_id,
            "department_name": state.get("department_name"),
            "responsible_person": state.get("responsible_person"),
            "draft_content": state.get("draft_content"),
            "iteration_count": int(state.get("iteration_count", 0)),
            "action": "department_approval_required",
        }

        raw_decision = interrupt(interrupt_request)
        if isinstance(raw_decision, dict) and "department_id" not in raw_decision:
            raw_decision = {**raw_decision, "department_id": dept_id}

        validated = validate_resume_decision(raw_decision)
        decision = validated["decision"]
        approver = validated["approver"]
        feedback = validated["feedback"]

        if decision == "approve":
            next_status = "approved"
        elif decision == "reject":
            next_status = "rejected"
        else:
            next_status = "changes_requested"

        updates: Dict[str, Any] = {
            "approval_status": next_status,
            "approver": approver,
            "review_feedback": feedback,
        }
        updates["execution_trace"] = record_execution_trace(
            state=dict(state),
            node_name="human_approval_checkpoint",
            input_snapshot=interrupt_request,
            output_snapshot=updates,
            department_id=dept_id,
        )
        return updates

    @traced_node("finalize_branch_approval")
    def _node_finalize_branch_approval(
        self, state: DepartmentBranchApprovalState
    ) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "approval_status": "approved",
            "approved_at": now_iso,
        }

    @traced_node("finalize_branch_rejection")
    def _node_finalize_branch_rejection(
        self, state: DepartmentBranchApprovalState
    ) -> Dict[str, Any]:
        return {
            "approval_status": "rejected",
            "approved_at": None,
        }

    @traced_node("revise_department_draft")
    def _node_revise_department_draft(
        self, state: DepartmentBranchApprovalState
    ) -> Dict[str, Any]:
        dept_id = state["department_id"]
        next_iter = int(state.get("iteration_count", 0)) + 1
        meta = dict(state.get("rfp_metadata") or {})
        feedback = state.get("review_feedback") or "Human reviewer requested revisions."
        sec_ctx = {
            "department_id": dept_id,
            "department_name": state.get("department_name"),
            "responsible_person": state.get("responsible_person"),
            "key_aspects": dict(state.get("key_aspects") or {}),
            "open_questions": list(state.get("open_questions") or []),
            "policy_warnings": list(state.get("policy_warnings") or []),
        }

        generator = self._get_generator(dept_id)
        revised_draft = generator.generate(
            rfp_metadata=meta,
            section_context=sec_ctx,
            feedback_for_generator=feedback,
            iteration=next_iter + 1,
        )
        if feedback and feedback not in revised_draft:
            revised_draft = (
                f"{revised_draft}\n\n"
                f"### Human Review Revision (Iteration {next_iter})\n"
                f"Addressed feedback from {state.get('approver') or state.get('responsible_person')}: {feedback}"
            )

        eval_result = self.evaluator.evaluate(
            department_id=dept_id,
            draft_text=revised_draft,
            client_country=str(meta.get("client_country") or "ES"),
            key_aspects=dict(state.get("key_aspects") or {}),
            open_questions=list(state.get("open_questions") or []),
            iteration=min(next_iter + 1, 3),
        )
        eval_history = list(state.get("evaluation_results") or [])
        eval_history.append(eval_result.to_schema_dict())

        return {
            "draft_content": revised_draft,
            "iteration_count": next_iter,
            "evaluation_results": eval_history,
            "approval_status": "pending",
        }

    @traced_node("escalate_branch_to_commercial")
    def _node_escalate_branch_to_commercial(
        self, state: DepartmentBranchApprovalState
    ) -> Dict[str, Any]:
        dept_id = state["department_id"]
        max_rev = int(state.get("max_revisions", self.max_revisions))
        note = (
            f"Escalated to {COMMERCIAL_DIRECTOR} (Commercial Director): "
            f"department '{dept_id}' reached maximum revision cap ({max_rev} revisions) "
            "without approval."
        )
        return {
            "approval_status": "needs_human_review",
            "escalation_note": note,
            "approved_at": None,
        }

    # -------------------------------------------------------------------------
    # High-Level Lifecycle Entrypoints
    # -------------------------------------------------------------------------

    def start_approval_phase(
        self,
        ticket_id: UUID,
        rfp_metadata: Optional[Dict[str, Any]] = None,
        department_sections: Optional[Dict[str, Dict[str, Any]]] = None,
        run_initial_arbitration: bool = False,
    ) -> Dict[str, Any]:
        """Enter Part 3 approval milestone: transition ticket to `esperando_aprobación` and pause each active branch in a scoped `interrupt()`."""
        meta, sections = self._load_or_merge_ticket_context(
            ticket_id=ticket_id,
            rfp_metadata=rfp_metadata,
            department_sections=department_sections,
        )

        raw_depts = meta.get("departments_needed") or list(sections.keys())
        active_departments: List[DepartmentIdLiteral] = [
            d for d in raw_depts if d in VALID_DEPARTMENTS
        ]

        arbitration_logs: List[ArbitrationLog] = []
        arb_traces: List[ExecutionTraceEntryDict] = []
        if run_initial_arbitration:
            arb_state = arbitration_node(
                {
                    "ticket_id": str(ticket_id),
                    "rfp_metadata": meta,
                    "department_sections": sections,
                    "max_revisions": self.max_revisions,
                    "arbitration_logs": [],
                    "execution_trace": [],
                }
            )
            meta = arb_state["rfp_metadata"]
            sections = arb_state["department_sections"]
            arb_traces = list(arb_state.get("execution_trace") or [])
            for log_dict in arb_state.get("arbitration_logs", []):
                log_entry = ArbitrationLog(
                    id=UUID(log_dict["id"]),
                    ticket_id=ticket_id,
                    trigger_id=log_dict["trigger_id"],
                    arbiter=log_dict["arbiter"],
                    rule_applied=log_dict["rule_applied"],
                    resolution_details=log_dict["resolution_details"],
                    created_at=datetime.fromisoformat(log_dict["created_at"]),
                )
                arbitration_logs.append(log_entry)
                if self.repository is not None:
                    self.repository.save_arbitration_log(log_entry)

        if self.repository is not None:
            ticket = self.repository.get_ticket(ticket_id)
            if ticket is not None:
                ticket.mark_waiting_for_approval()
                self.repository.save_ticket(ticket)

        branch_statuses: Dict[str, str] = {}
        traces: List[ExecutionTraceEntryDict] = list(arb_traces)

        for dept_id in active_departments:
            sec = sections.get(dept_id) or {}
            default_name, default_lead = DEPARTMENT_LEADS[dept_id]
            initial_branch_state: DepartmentBranchApprovalState = {
                "ticket_id": str(ticket_id),
                "department_id": dept_id,
                "department_name": str(sec.get("department_name") or default_name),
                "responsible_person": str(sec.get("responsible_person") or default_lead),
                "rfp_metadata": meta,
                "key_aspects": dict(sec.get("key_aspects") or {}),
                "open_questions": list(sec.get("open_questions") or []),
                "policy_warnings": list(sec.get("policy_warnings") or []),
                "draft_content": str(sec.get("draft_content") or ""),
                "evaluation_results": list(sec.get("evaluation_results") or []),
                "approval_status": "pending",
                "approver": None,
                "review_feedback": sec.get("review_feedback"),
                "iteration_count": int(sec.get("iteration_count", 0) or 0),
                "max_revisions": self.max_revisions,
                "approved_at": None,
                "escalation_note": None,
                "execution_trace": [],
            }

            config = make_branch_config(ticket_id, dept_id)
            self.branch_graph.invoke(initial_branch_state, config=config)
            snapshot = self.branch_graph.get_state(config)
            is_interrupted = bool(snapshot.next)
            branch_statuses[dept_id] = "interrupted" if is_interrupted else "pending"
            traces.extend(snapshot.values.get("execution_trace") or [])

            if self.repository is not None:
                self.repository.update_department_section_approval(
                    ticket_id=ticket_id,
                    department_id=dept_id,
                    approval_status="pending",
                    draft_content=initial_branch_state["draft_content"],
                )

        return {
            "ticket_id": str(ticket_id),
            "ticket_status": TicketStatus.WAITING_FOR_APPROVAL.value,
            "active_departments": active_departments,
            "branch_statuses": branch_statuses,
            "arbitration_logs": [log.to_schema_dict() for log in arbitration_logs],
            "execution_trace": traces,
        }

    def get_branch_snapshot(
        self,
        ticket_id: UUID,
        department_id: DepartmentIdLiteral,
    ) -> Any:
        """Retrieve current LangGraph StateSnapshot for a namespaced department branch."""
        config = make_branch_config(ticket_id, department_id)
        return self.branch_graph.get_state(config)

    def is_branch_interrupted(
        self,
        ticket_id: UUID,
        department_id: DepartmentIdLiteral,
    ) -> bool:
        """Return True if the specified department branch is currently paused at an `interrupt()`."""
        snapshot = self.get_branch_snapshot(ticket_id, department_id)
        return bool(snapshot and snapshot.next)

    def resume_department_approval(
        self,
        ticket_id: UUID,
        department_id: DepartmentIdLiteral,
        decision: ApprovalDecisionLiteral,
        approver: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate human decision and resume ONLY the target department branch from its paused checkpoint."""
        validated = validate_resume_decision(
            {
                "department_id": department_id,
                "decision": decision,
                "approver": approver,
                "feedback": feedback,
            }
        )

        config = make_branch_config(ticket_id, department_id)
        snapshot = self.branch_graph.get_state(config)
        if not snapshot or not snapshot.values:
            raise BranchNotInterruptedError(
                f"Branch '{format_branch_thread_id(ticket_id, department_id)}' has no active checkpoint."
            )

        current_approval_status = snapshot.values.get("approval_status")
        if not snapshot.next:
            if (
                current_approval_status == "rejected"
                and decision in ("request_changes", "approve")
            ) or (
                current_approval_status == "needs_human_review"
                and decision in ("approve", "reject", "request_changes")
            ):
                branch_state = dict(snapshot.values)
                branch_state["review_feedback"] = validated.get("feedback")
                branch_state["approver"] = validated.get("approver")
                if decision == "request_changes":
                    branch_state["approval_status"] = "pending"
                    if current_approval_status == "needs_human_review":
                        branch_state["max_revisions"] = (
                            int(branch_state.get("iteration_count", 0)) + 1
                        )
                    revised_update = self._node_revise_department_draft(branch_state)
                    branch_state.update(revised_update)
                    self.branch_graph.invoke(branch_state, config=config)
                elif decision in ("approve", "reject"):
                    branch_state["approval_status"] = "pending"
                    self.branch_graph.invoke(branch_state, config=config)
                    self.branch_graph.invoke(Command(resume=validated), config=config)
                after_snapshot = self.branch_graph.get_state(config)
                branch_state = dict(after_snapshot.values or branch_state)
            else:
                raise BranchNotInterruptedError(
                    f"Department branch '{department_id}' for ticket '{ticket_id}' is not currently paused in an interrupt "
                    f"(current approval_status='{current_approval_status}')."
                )
        else:
            resumed_values = self.branch_graph.invoke(
                Command(resume=validated),
                config=config,
            )
            after_snapshot = self.branch_graph.get_state(config)
            branch_state = dict(after_snapshot.values or resumed_values)

        # Determine effective persisted approval status
        if after_snapshot.next and validated["decision"] == "request_changes":
            # Branch revised draft and re-paused at interrupt for next human review cycle
            effective_approval_status = "changes_requested"
        else:
            effective_approval_status = str(
                branch_state.get("approval_status") or "pending"
            )

        approved_at_str: Optional[str] = branch_state.get("approved_at")
        approved_at_dt: Optional[datetime] = (
            datetime.fromisoformat(approved_at_str)
            if isinstance(approved_at_str, str)
            else None
        )
        iteration_count = int(branch_state.get("iteration_count", 0))
        draft_content = str(branch_state.get("draft_content") or "")

        if self.repository is not None:
            self.repository.update_department_section_approval(
                ticket_id=ticket_id,
                department_id=department_id,
                approval_status=effective_approval_status,
                approver=validated["approver"],
                review_feedback=validated["feedback"],
                iteration=iteration_count,
                draft_content=draft_content,
                approved_at=approved_at_dt,
            )

        # Check all active branches for this ticket to see if 100% are approved
        ticket_status, final_doc, gate_traces = self._evaluate_ticket_completion_gate(ticket_id)
        merged_traces = list(branch_state.get("execution_trace") or [])
        merged_traces.extend(gate_traces)

        return {
            "ticket_id": str(ticket_id),
            "department_id": department_id,
            "approval_status": effective_approval_status,
            "ticket_status": ticket_status,
            "iteration_count": iteration_count,
            "approved_at": approved_at_str,
            "draft_content": draft_content,
            "escalation_note": branch_state.get("escalation_note"),
            "final_document": final_doc.to_schema_dict() if final_doc else None,
            "execution_trace": merged_traces,
            "message": self._build_resume_message(
                department_id=department_id,
                approval_status=effective_approval_status,
                ticket_status=ticket_status,
            ),
        }

    def _evaluate_ticket_completion_gate(
        self,
        ticket_id: UUID,
    ) -> Tuple[str, Optional[FinalDocument], List[ExecutionTraceEntryDict]]:
        """Check whether all active department branches have approved; if so, run arbitration & final synthesis."""
        meta, sections = self._load_or_merge_ticket_context(ticket_id)
        raw_depts = meta.get("departments_needed") or list(sections.keys())
        active_departments: List[DepartmentIdLiteral] = [
            d for d in raw_depts if d in VALID_DEPARTMENTS
        ]

        # Overlay latest state from checkpointer for each active branch
        for dept_id in active_departments:
            snap = self.get_branch_snapshot(ticket_id, dept_id)
            if snap and snap.values:
                b_vals = snap.values
                sec_entry = dict(sections.get(dept_id) or {})
                if snap.next and b_vals.get("review_feedback"):
                    sec_entry["approval_status"] = (
                        "changes_requested"
                        if b_vals.get("iteration_count", 0) > 0
                        else "pending"
                    )
                else:
                    sec_entry["approval_status"] = b_vals.get("approval_status", "pending")
                sec_entry["approver"] = b_vals.get("approver")
                sec_entry["approved_at"] = b_vals.get("approved_at")
                sec_entry["draft_content"] = b_vals.get("draft_content") or sec_entry.get("draft_content")
                sec_entry["department_name"] = b_vals.get("department_name") or sec_entry.get("department_name")
                sec_entry["responsible_person"] = b_vals.get("responsible_person") or sec_entry.get("responsible_person")
                sec_entry["key_aspects"] = b_vals.get("key_aspects") or sec_entry.get("key_aspects") or {}
                sec_entry["iteration_count"] = int(b_vals.get("iteration_count", 0))
                sections[dept_id] = sec_entry

        # Check if any branch escalated to needs_human_review
        any_escalated = any(
            sections.get(d, {}).get("approval_status") == "needs_human_review"
            for d in active_departments
        )
        if any_escalated:
            if self.repository is not None:
                ticket = self.repository.get_ticket(ticket_id)
                if ticket is not None:
                    ticket.mark_needs_human_review(
                        error_message=f"Escalated to {COMMERCIAL_DIRECTOR}: department revision limit reached."
                    )
                    self.repository.save_ticket(ticket)
            return TicketStatus.NEEDS_HUMAN_REVIEW.value, None, []

        # Check if any branch was rejected
        rejected_depts = [
            d for d in active_departments if sections.get(d, {}).get("approval_status") == "rejected"
        ]
        if rejected_depts:
            first_rejected = rejected_depts[0]
            feedback = (
                sections.get(first_rejected, {}).get("review_feedback")
                or "Department rejected proposal."
            )
            err_msg = (
                f"Escalated to {COMMERCIAL_DIRECTOR} (Commercial Director): "
                f"department '{first_rejected}' rejected proposal: {feedback}"
            )
            if self.repository is not None:
                ticket = self.repository.get_ticket(ticket_id)
                if ticket is not None:
                    ticket.mark_needs_human_review(error_message=err_msg)
                    self.repository.save_ticket(ticket)
            return TicketStatus.NEEDS_HUMAN_REVIEW.value, None, []

        if not can_synthesize_final_document(active_departments, sections):
            if self.repository is not None:
                ticket = self.repository.get_ticket(ticket_id)
                if ticket is not None and ticket.status != TicketStatus.WAITING_FOR_APPROVAL:
                    ticket.mark_waiting_for_approval()
                    self.repository.save_ticket(ticket)
            return TicketStatus.WAITING_FOR_APPROVAL.value, None, []

        gate_traces: List[ExecutionTraceEntryDict] = []

        # All active departments approved -> Run deterministic conflict check before synthesis via traced arbitration_node
        arb_state = arbitration_node(
            {
                "ticket_id": str(ticket_id),
                "rfp_metadata": meta,
                "department_sections": sections,
                "max_revisions": self.max_revisions,
                "arbitration_logs": [],
                "execution_trace": [],
            }
        )
        updated_meta = arb_state["rfp_metadata"]
        updated_sections = arb_state["department_sections"]
        gate_traces.extend(arb_state.get("execution_trace") or [])

        if self.repository is not None:
            for log_dict in arb_state.get("arbitration_logs", []):
                log_entry = ArbitrationLog(
                    id=UUID(log_dict["id"]),
                    ticket_id=ticket_id,
                    trigger_id=log_dict["trigger_id"],
                    arbiter=log_dict["arbiter"],
                    rule_applied=log_dict["rule_applied"],
                    resolution_details=log_dict["resolution_details"],
                    created_at=datetime.fromisoformat(log_dict["created_at"]),
                )
                self.repository.save_arbitration_log(log_entry)

        # If arbitration forced a section back into changes_requested or rejected, block synthesis!
        if not can_synthesize_final_document(active_departments, updated_sections):
            if self.repository is not None:
                for dept_id, sec_data in updated_sections.items():
                    self.repository.update_department_section_approval(
                        ticket_id=ticket_id,
                        department_id=dept_id,
                        approval_status=str(sec_data.get("approval_status", "changes_requested")),
                        review_feedback=sec_data.get("review_feedback"),
                        draft_content=sec_data.get("draft_content"),
                    )
            if any(updated_sections.get(d, {}).get("approval_status") == "rejected" for d in active_departments):
                return TicketStatus.NEEDS_HUMAN_REVIEW.value, None, gate_traces
            return TicketStatus.WAITING_FOR_APPROVAL.value, None, gate_traces

        # Synthesize final document via traced final_synthesis_node
        synth_state = final_synthesis_node(
            {
                "ticket_id": str(ticket_id),
                "rfp_metadata": updated_meta,
                "department_sections": updated_sections,
                "active_departments": active_departments,
                "execution_trace": gate_traces,
            }
        )
        gate_traces = list(synth_state.get("execution_trace") or [])
        final_doc_dict = synth_state["final_document"]
        final_doc = FinalDocument(
            id=UUID(final_doc_dict["id"]),
            ticket_id=ticket_id,
            title=final_doc_dict["title"],
            client_name=final_doc_dict["client_name"],
            currency=final_doc_dict["currency"],
            executive_summary=final_doc_dict["executive_summary"],
            sections=final_doc_dict["sections"],
            generated_at=datetime.fromisoformat(final_doc_dict["generated_at"]),
        )

        if self.repository is not None:
            self.repository.save_final_document(final_doc)
            ticket = self.repository.get_ticket(ticket_id)
            if ticket is not None:
                ticket.mark_terminado()
                self.repository.save_ticket(ticket)

        return TicketStatus.TERMINADO.value, final_doc, gate_traces

    def _load_or_merge_ticket_context(
        self,
        ticket_id: UUID,
        rfp_metadata: Optional[Dict[str, Any]] = None,
        department_sections: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        meta: Dict[str, Any] = dict(rfp_metadata or {})
        sections: Dict[str, Dict[str, Any]] = dict(department_sections or {})

        if self.repository is not None:
            if not meta:
                meta_entity = self.repository.get_metadata(ticket_id)
                part3_handoff = self.repository.get_part3_handoff_payload(ticket_id)
                if meta_entity is not None:
                    meta = {
                        "client_name": meta_entity.client_name,
                        "client_country": meta_entity.client_country,
                        "currency": meta_entity.currency,
                        "services_requested": list(meta_entity.services_requested),
                        "monthly_volume": meta_entity.monthly_volume,
                        "deadline": meta_entity.deadline,
                        "budget_range": meta_entity.budget_range,
                        "departments_needed": list(meta_entity.departments_needed),
                    }
                elif part3_handoff is not None:
                    meta = dict(part3_handoff.rfp_metadata)

            if not sections:
                db_sections = self.repository.list_department_sections(ticket_id)
                for sec in db_sections:
                    sections[sec.department_id] = {
                        "department_id": sec.department_id,
                        "department_name": sec.department_name,
                        "responsible_person": sec.responsible_person,
                        "key_aspects": dict(sec.key_aspects),
                        "open_questions": list(sec.open_questions),
                        "policy_warnings": list(sec.policy_warnings),
                        "draft_content": sec.draft_content or "",
                        "evaluation_results": list(sec.evaluation_results),
                        "approval_status": sec.approval_status,
                        "approver": sec.approver,
                        "review_feedback": sec.review_feedback,
                        "iteration_count": (
                            sec.iteration
                            if sec.approval_status in ("changes_requested", "needs_human_review")
                            else 0
                        ),
                        "approved_at": (
                            sec.approved_at.isoformat()
                            if isinstance(sec.approved_at, datetime)
                            else sec.approved_at
                        ),
                    }

        return meta, sections

    @staticmethod
    def _build_resume_message(
        department_id: str,
        approval_status: str,
        ticket_status: str,
    ) -> str:
        if ticket_status == TicketStatus.TERMINADO.value:
            return (
                f"Department '{department_id}' approved. All active departments have approved; "
                "final commercial proposal document synthesized and ticket marked 'terminado'."
            )
        if approval_status == "approved":
            return (
                f"Department '{department_id}' approved independently. "
                "Ticket remains in 'esperando_aprobación' awaiting remaining active departments."
            )
        if approval_status == "changes_requested":
            return (
                f"Changes requested for department '{department_id}'. "
                "Draft revised and re-paused at human review checkpoint."
            )
        if approval_status == "needs_human_review":
            return (
                f"Department '{department_id}' reached maximum revision cap and was escalated to {COMMERCIAL_DIRECTOR}."
            )
        return f"Department '{department_id}' decision recorded with status '{approval_status}'."


__all__ = [
    "BranchNotInterruptedError",
    "DEFAULT_MAX_REVISIONS",
    "RFPApprovalCompletionPipeline",
    "ResumeValidationError",
    "arbitration_node",
    "final_synthesis_node",
    "validate_resume_decision",
]
