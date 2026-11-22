"""Dedicated RFP Response Generation & Department Drafting Pipeline (Part 2 of 3).

Coordinates:
1. Direct ingestion of Part 1 handoff payload from PostgreSQL without re-parsing raw PDFs.
2. Independent generator-evaluator feedback loops per active department (warehouse, lastmile, reverse).
3. Strict iteration cap enforcement (default max 3 total attempts = initial + 2 revisions).
4. Graceful escalation to 'needs_human_review' upon iteration cap exhaustion (never discarding ticket).
5. Compilation and persistence of the canonical Part 3 handoff payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Literal, Optional
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.agent.rfp_generator_agents import (  # noqa: E402
    BaseDepartmentGeneratorAgent,
    KnowledgeRetrievalHelper,
    get_department_generator_agent,
)
from data.pipelines.rfp_response_generation.evaluator import (  # noqa: E402
    DepartmentSectionEvaluator,
)
from domain.rfp.entities import (  # noqa: E402
    DepartmentSection,
    EvaluationResult,
    Part3HandoffPayload,
    TicketStatus,
)
from domain.rfp.ports import IntakeTicketRepositoryPort  # noqa: E402

logger = logging.getLogger("rfp_response_generation_pipeline")

DEFAULT_MAX_ATTEMPTS = 3
PART3_HANDOFF_SCHEMA_VERSION = "2.0.0"

DepartmentIdLiteral = Literal["warehouse", "lastmile", "reverse"]


@dataclass
class DepartmentLoopOutcome:
    """Outcome of an isolated generator-evaluator loop for a single department."""

    department_id: DepartmentIdLiteral
    draft_content: str
    status: Literal["passed", "needs_human_review"]
    iteration: int
    latest_evaluation: EvaluationResult
    evaluation_history: List[EvaluationResult]


def compile_part3_handoff_payload(
    ticket_id: UUID,
    rfp_metadata: Dict[str, Any],
    outcomes: Dict[str, DepartmentLoopOutcome],
    handoff_id: Optional[UUID] = None,
) -> Part3HandoffPayload:
    """Compile the canonical Part 3 handoff package matching part3-handoff.schema.json."""
    any_flagged = any(
        outcome.status == "needs_human_review" for outcome in outcomes.values()
    )
    overall_status: Literal["passed", "needs_human_review"] = (
        "needs_human_review" if any_flagged else "passed"
    )

    sanitized_metadata: Dict[str, Any] = {
        "client_name": str(rfp_metadata.get("client_name") or "Prospective Client"),
        "client_country": str(rfp_metadata.get("client_country") or "ES"),
        "currency": str(rfp_metadata.get("currency") or "EUR"),
        "monthly_volume": rfp_metadata.get("monthly_volume"),
        "deadline": rfp_metadata.get("deadline"),
        "departments_needed": list(rfp_metadata.get("departments_needed") or list(outcomes.keys())),
    }

    dept_sections_bundle: Dict[str, Any] = {}
    for dept_id, outcome in outcomes.items():
        dept_sections_bundle[dept_id] = {
            "draft_content": outcome.draft_content,
            "status": outcome.status,
            "iteration": outcome.iteration,
            "evaluation_result": outcome.latest_evaluation.to_schema_dict(),
        }

    return Part3HandoffPayload(
        id=handoff_id or uuid4(),
        ticket_id=ticket_id,
        schema_version=PART3_HANDOFF_SCHEMA_VERSION,
        overall_status=overall_status,
        rfp_metadata=sanitized_metadata,
        department_sections=dept_sections_bundle,
        emitted_at=datetime.now(timezone.utc),
    )


class RFPResponseGenerationPipeline:
    """Orchestrates Part 2 per-department proposal drafting, parallel evaluation, and Part 3 handoff."""

    def __init__(
        self,
        repository: Optional[IntakeTicketRepositoryPort] = None,
        evaluator: Optional[DepartmentSectionEvaluator] = None,
        generators: Optional[Dict[str, BaseDepartmentGeneratorAgent]] = None,
        knowledge_helper: Optional[KnowledgeRetrievalHelper] = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.repository = repository
        self.evaluator = evaluator or DepartmentSectionEvaluator()
        self.knowledge_helper = knowledge_helper or KnowledgeRetrievalHelper()
        self.generators: Dict[str, BaseDepartmentGeneratorAgent] = generators or {}
        self.max_attempts = min(max_attempts, 3)

    def _get_generator(
        self, department_id: DepartmentIdLiteral
    ) -> BaseDepartmentGeneratorAgent:
        if department_id in self.generators:
            return self.generators[department_id]
        return get_department_generator_agent(
            department_id, knowledge_helper=self.knowledge_helper
        )

    def run_department_loop(
        self,
        ticket_id: UUID,
        department_id: DepartmentIdLiteral,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
    ) -> DepartmentLoopOutcome:
        """Execute the isolated generator-evaluator revision loop for a single department.

        Enforces the iteration cap (max_attempts, default 3 = 1 initial + 2 revisions).
        If overall_pass remains False after max_attempts, marks section as 'needs_human_review'
        and retains the latest draft and EvaluationResult.
        """
        generator = self._get_generator(department_id)
        client_country = str(rfp_metadata.get("client_country") or "ES")
        key_aspects: Dict[str, Any] = dict(section_context.get("key_aspects") or {})
        open_questions: List[str] = list(section_context.get("open_questions") or [])

        feedback: Optional[str] = None
        draft_content = ""
        latest_eval: Optional[EvaluationResult] = None
        history: List[EvaluationResult] = []
        final_status: Literal["passed", "needs_human_review"] = "needs_human_review"
        current_iteration = 0

        for attempt in range(1, self.max_attempts + 1):
            current_iteration = attempt

            if self.repository is not None:
                self.repository.update_department_section_draft(
                    ticket_id=ticket_id,
                    department_id=department_id,
                    draft_content=draft_content or None,
                    iteration=attempt,
                    status="drafting",
                    evaluation_result=None,
                )

            # 1. Generate or revise draft ( passing feedback on attempt > 1 )
            draft_content = generator.generate(
                rfp_metadata=rfp_metadata,
                section_context=section_context,
                feedback_for_generator=feedback,
                iteration=attempt,
            )

            if self.repository is not None:
                self.repository.update_department_section_draft(
                    ticket_id=ticket_id,
                    department_id=department_id,
                    draft_content=draft_content,
                    iteration=attempt,
                    status="under_evaluation",
                    evaluation_result=None,
                )

            # 2. Evaluate draft across Readability, Relevance, and Compliance in parallel
            eval_result = self.evaluator.evaluate(
                department_id=department_id,
                draft_text=draft_content,
                client_country=client_country,
                key_aspects=key_aspects,
                open_questions=open_questions,
                iteration=attempt,
            )
            latest_eval = eval_result
            history.append(eval_result)

            if eval_result.overall_pass:
                final_status = "passed"
                if self.repository is not None:
                    self.repository.update_department_section_draft(
                        ticket_id=ticket_id,
                        department_id=department_id,
                        draft_content=draft_content,
                        iteration=attempt,
                        status="passed",
                        evaluation_result=eval_result,
                    )
                break

            # Failed evaluation on this attempt
            if attempt < self.max_attempts:
                feedback = eval_result.feedback_for_generator
                if self.repository is not None:
                    self.repository.update_department_section_draft(
                        ticket_id=ticket_id,
                        department_id=department_id,
                        draft_content=draft_content,
                        iteration=attempt,
                        status="drafting",
                        evaluation_result=eval_result,
                    )
            else:
                # Exhausted iteration cap -> escalate to needs_human_review
                final_status = "needs_human_review"
                if self.repository is not None:
                    self.repository.update_department_section_draft(
                        ticket_id=ticket_id,
                        department_id=department_id,
                        draft_content=draft_content,
                        iteration=attempt,
                        status="needs_human_review",
                        evaluation_result=eval_result,
                    )

        assert latest_eval is not None
        return DepartmentLoopOutcome(
            department_id=department_id,
            draft_content=draft_content,
            status=final_status,
            iteration=current_iteration,
            latest_evaluation=latest_eval,
            evaluation_history=history,
        )

    def execute_from_handoff(
        self,
        ticket_id: UUID,
        rfp_metadata: Dict[str, Any],
        department_sections: Dict[str, Dict[str, Any]],
    ) -> Part3HandoffPayload:
        """Run Part 2 proposal generation from an in-memory Part 1 handoff structure without PDF re-parsing."""
        if self.repository is not None:
            ticket = self.repository.get_ticket(ticket_id)
            if ticket is not None:
                ticket.mark_drafting()
                self.repository.save_ticket(ticket)

        raw_depts = rfp_metadata.get("departments_needed") or list(department_sections.keys())
        active_departments: List[DepartmentIdLiteral] = [
            d for d in raw_depts if d in ("warehouse", "lastmile", "reverse")
        ]

        if self.repository is not None:
            ticket = self.repository.get_ticket(ticket_id)
            if ticket is not None:
                ticket.mark_under_evaluation()
                self.repository.save_ticket(ticket)

        outcomes: Dict[str, DepartmentLoopOutcome] = {}
        for dept_id in active_departments:
            sec_ctx = department_sections.get(dept_id) or {
                "department_id": dept_id,
                "key_aspects": {},
                "open_questions": [],
                "policy_warnings": [],
            }
            outcomes[dept_id] = self.run_department_loop(
                ticket_id=ticket_id,
                department_id=dept_id,
                rfp_metadata=rfp_metadata,
                section_context=sec_ctx,
            )

        part3_payload = compile_part3_handoff_payload(
            ticket_id=ticket_id,
            rfp_metadata=rfp_metadata,
            outcomes=outcomes,
        )

        if self.repository is not None:
            self.repository.save_part3_handoff_payload(part3_payload)
            ticket = self.repository.get_ticket(ticket_id)
            if ticket is not None:
                if part3_payload.overall_status == "needs_human_review":
                    ticket.mark_needs_human_review()
                else:
                    # Keep in Part 2 under_evaluation (never set Part 3 statuses)
                    ticket.mark_under_evaluation()
                self.repository.save_ticket(ticket)

        return part3_payload

    def execute_for_ticket(self, ticket_id: UUID) -> Part3HandoffPayload:
        """Load Part 1 handoff artifacts from PostgreSQL and execute Part 2 pipeline."""
        if self.repository is None:
            raise RuntimeError("Repository is required for execute_for_ticket.")

        ticket = self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket '{ticket_id}' not found.")

        metadata_entity = self.repository.get_metadata(ticket_id)
        handoff_entity = self.repository.get_handoff_payload(ticket_id)
        sections_list = self.repository.list_department_sections(ticket_id)

        if metadata_entity is not None:
            rfp_metadata: Dict[str, Any] = {
                "client_name": metadata_entity.client_name,
                "client_country": metadata_entity.client_country,
                "currency": metadata_entity.currency,
                "services_requested": list(metadata_entity.services_requested),
                "monthly_volume": metadata_entity.monthly_volume,
                "deadline": metadata_entity.deadline,
                "budget_range": metadata_entity.budget_range,
                "departments_needed": list(metadata_entity.departments_needed),
            }
        elif handoff_entity is not None and "metadata" in handoff_entity.full_handoff_json:
            rfp_metadata = dict(handoff_entity.full_handoff_json["metadata"])
        else:
            raise ValueError(f"Part 1 RFP metadata not found for ticket '{ticket_id}'.")

        department_sections_map: Dict[str, Dict[str, Any]] = {}
        for sec in sections_list:
            department_sections_map[sec.department_id] = {
                "department_id": sec.department_id,
                "department_name": sec.department_name,
                "responsible_person": sec.responsible_person,
                "key_aspects": dict(sec.key_aspects),
                "open_questions": list(sec.open_questions),
                "policy_warnings": list(sec.policy_warnings),
            }

        # Ensure any active department without a pre-existing row has a default section record
        dept_defaults = {
            "warehouse": ("Operaciones de Almacén", "Ana Whitfield"),
            "lastmile": ("Transporte y Última Milla", "Carlos Vega"),
            "reverse": ("Logística Inversa y Devoluciones", "Sofía Ramos"),
        }
        for dept_id in rfp_metadata.get("departments_needed", []):
            if dept_id in dept_defaults and dept_id not in department_sections_map:
                d_name, d_person = dept_defaults[dept_id]
                new_sec = DepartmentSection(
                    id=uuid4(),
                    ticket_id=ticket_id,
                    department_id=dept_id,
                    department_name=d_name,
                    responsible_person=d_person,
                    key_aspects={},
                    open_questions=[],
                    policy_warnings=[],
                )
                self.repository.save_department_section(new_sec)
                department_sections_map[dept_id] = {
                    "department_id": dept_id,
                    "department_name": d_name,
                    "responsible_person": d_person,
                    "key_aspects": {},
                    "open_questions": [],
                    "policy_warnings": [],
                }

        return self.execute_from_handoff(
            ticket_id=ticket_id,
            rfp_metadata=rfp_metadata,
            department_sections=department_sections_map,
        )
