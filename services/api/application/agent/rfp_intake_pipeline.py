"""LangGraph multi-agent orchestration pipeline for RFP Intake & Analysis."""

from dataclasses import asdict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Literal, Optional, TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session

from application.agent.rfp_classifier_agent import RFPClassifierAgent
from application.agent.rfp_department_workers import (
    LastMileWorker,
    ReverseWorker,
    WarehouseWorker,
)
from application.agent.rfp_orchestrator_agent import RFPOrchestratorAgent
from application.agent.rfp_synthesizer_agent import RFPSynthesizerAgent
from domain.rfp.entities import (
    DepartmentSection,
    IntakeHandoffPayload,
    IntakeTicket,
    ReadabilityScores,
    RFPMetadata,
    TicketStatus,
)
from domain.rfp.exceptions import DocumentParseError
from infrastructure.adapters.pdf_to_markdown_adapter import PdfToMarkdownAdapter
from infrastructure.adapters.textstat_readability import TextstatReadabilityAdapter
from infrastructure.persistence.sqlmodel.client import get_engine
from infrastructure.persistence.sqlmodel.rfp_repository import SQLModelIntakeTicketRepository

logger = logging.getLogger("rfp_intake_pipeline")


class RFPState(TypedDict):
    """Typed state passed across LangGraph nodes."""

    ticket_id: str
    pdf_path: str
    markdown_content: str
    readability_scores: Dict[str, Any]
    is_rfp: bool
    rejection_reason: Optional[str]
    metadata: Optional[Dict[str, Any]]
    department_sections: Dict[str, Any]
    synthesis: Optional[Dict[str, Any]]
    status: str
    error_message: Optional[str]


def create_initial_state(ticket_id: UUID, pdf_path: str) -> RFPState:
    """Initialize empty state for pipeline execution."""
    return {
        "ticket_id": str(ticket_id),
        "pdf_path": pdf_path,
        "markdown_content": "",
        "readability_scores": {},
        "is_rfp": False,
        "rejection_reason": None,
        "metadata": None,
        "department_sections": {},
        "synthesis": None,
        "status": TicketStatus.ANALIZANDO.value,
        "error_message": None,
    }


class RFPIntakePipeline:
    """Encapsulates the compiled LangGraph workflow for proposal intake."""

    def __init__(self, repository: Optional[SQLModelIntakeTicketRepository] = None) -> None:
        self.converter = PdfToMarkdownAdapter()
        self.readability = TextstatReadabilityAdapter()
        self.classifier = RFPClassifierAgent()
        self.orchestrator = RFPOrchestratorAgent()
        self.warehouse_worker = WarehouseWorker()
        self.lastmile_worker = LastMileWorker()
        self.reverse_worker = ReverseWorker()
        self.synthesizer = RFPSynthesizerAgent()
        self.repository = repository
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(RFPState)

        # Register nodes
        builder.add_node("ingest_and_convert", self._node_ingest_and_convert)
        builder.add_node("classify", self._node_classify)
        builder.add_node("orchestrate", self._node_orchestrate)
        builder.add_node("warehouse_worker", self._node_warehouse_worker)
        builder.add_node("lastmile_worker", self._node_lastmile_worker)
        builder.add_node("reverse_worker", self._node_reverse_worker)
        builder.add_node("synthesize", self._node_synthesize)

        # Wire edges
        builder.add_edge(START, "ingest_and_convert")
        builder.add_edge("ingest_and_convert", "classify")

        # Conditional branch after classifier: if RFP continue to orchestrate, else END
        def after_classify(state: RFPState) -> str:
            return "orchestrate" if state["is_rfp"] else END

        builder.add_conditional_edges("classify", after_classify, ["orchestrate", END])

        # After orchestrate, route to active department workers
        # For simplicity in LangGraph sequential or fanout:
        builder.add_edge("orchestrate", "warehouse_worker")
        builder.add_edge("warehouse_worker", "lastmile_worker")
        builder.add_edge("lastmile_worker", "reverse_worker")
        builder.add_edge("reverse_worker", "synthesize")
        builder.add_edge("synthesize", END)

        return builder.compile()

    # -------------------------------------------------------------
    # Node implementations
    # -------------------------------------------------------------

    def _node_ingest_and_convert(self, state: RFPState) -> Dict[str, Any]:
        md_text = self.converter.convert_to_markdown(state["pdf_path"])
        scores = self.readability.calculate_scores(md_text)
        return {
            "markdown_content": md_text,
            "readability_scores": asdict(scores),
        }

    def _node_classify(self, state: RFPState) -> Dict[str, Any]:
        decision = self.classifier.classify(state["markdown_content"])
        if not decision.is_rfp:
            tid = UUID(state["ticket_id"])
            if self.repository:
                ticket = self.repository.get_ticket(tid)
                if ticket:
                    ticket.mark_discarded(decision.rejection_reason or "Non-RFP proposal.")
                    self.repository.save_ticket(ticket)
            return {
                "is_rfp": False,
                "rejection_reason": decision.rejection_reason,
                "status": TicketStatus.DESCARTADO.value,
            }

        return {
            "is_rfp": True,
            "rejection_reason": None,
        }

    def _node_orchestrate(self, state: RFPState) -> Dict[str, Any]:
        extracted = self.orchestrator.extract(state["markdown_content"])
        tid = UUID(state["ticket_id"])

        raw_scores = state.get("readability_scores", {})
        scores = ReadabilityScores(
            flesch_reading_ease=float(raw_scores.get("flesch_reading_ease", 0.0)),
            flesch_kincaid_grade=float(raw_scores.get("flesch_kincaid_grade", 0.0)),
            reading_level_label=str(raw_scores.get("reading_level_label", "Standard")),
            word_count=int(raw_scores.get("word_count", 0)),
            sentence_count=int(raw_scores.get("sentence_count", 0)),
        )

        metadata_entity = RFPMetadata(
            id=uuid4(),
            ticket_id=tid,
            client_name=extracted.client_name,
            client_country=extracted.client_country,
            currency=extracted.currency,
            services_requested=extracted.services_requested,
            monthly_volume=extracted.monthly_volume,
            deadline=extracted.deadline,
            budget_range=extracted.budget_range,
            departments_needed=extracted.departments_needed,
            unsupported_services=extracted.unsupported_services,
            readability_scores=scores,
        )

        if self.repository:
            self.repository.save_metadata(metadata_entity)

        return {
            "metadata": {
                "client_name": extracted.client_name,
                "client_country": extracted.client_country,
                "currency": extracted.currency,
                "services_requested": extracted.services_requested,
                "monthly_volume": extracted.monthly_volume,
                "deadline": extracted.deadline,
                "budget_range": extracted.budget_range,
                "departments_needed": extracted.departments_needed,
                "unsupported_services": extracted.unsupported_services,
                "readability_scores": asdict(scores),
            }
        }

    def _node_warehouse_worker(self, state: RFPState) -> Dict[str, Any]:
        meta = state.get("metadata") or {}
        departments_needed = meta.get("departments_needed", [])
        if "warehouse" not in departments_needed:
            return {}

        tid = UUID(state["ticket_id"])
        country = meta.get("client_country", "ES")
        section = self.warehouse_worker.analyze(tid, state["markdown_content"], country)

        if self.repository:
            self.repository.save_department_section(section)

        dept_sections = dict(state.get("department_sections", {}))
        dept_sections["warehouse"] = asdict(section)
        return {"department_sections": dept_sections}

    def _node_lastmile_worker(self, state: RFPState) -> Dict[str, Any]:
        meta = state.get("metadata") or {}
        departments_needed = meta.get("departments_needed", [])
        if "lastmile" not in departments_needed:
            return {}

        tid = UUID(state["ticket_id"])
        country = meta.get("client_country", "ES")
        section = self.lastmile_worker.analyze(tid, state["markdown_content"], country)

        if self.repository:
            self.repository.save_department_section(section)

        dept_sections = dict(state.get("department_sections", {}))
        dept_sections["lastmile"] = asdict(section)
        return {"department_sections": dept_sections}

    def _node_reverse_worker(self, state: RFPState) -> Dict[str, Any]:
        meta = state.get("metadata") or {}
        departments_needed = meta.get("departments_needed", [])
        if "reverse" not in departments_needed:
            return {}

        tid = UUID(state["ticket_id"])
        country = meta.get("client_country", "ES")
        section = self.reverse_worker.analyze(tid, state["markdown_content"], country)

        if self.repository:
            self.repository.save_department_section(section)

        dept_sections = dict(state.get("department_sections", {}))
        dept_sections["reverse"] = asdict(section)
        return {"department_sections": dept_sections}

    def _node_synthesize(self, state: RFPState) -> Dict[str, Any]:
        tid = UUID(state["ticket_id"])
        meta_dict = state.get("metadata") or {}
        raw_scores = meta_dict.get("readability_scores", {})
        scores = ReadabilityScores(
            flesch_reading_ease=float(raw_scores.get("flesch_reading_ease", 0.0)),
            flesch_kincaid_grade=float(raw_scores.get("flesch_kincaid_grade", 0.0)),
            reading_level_label=str(raw_scores.get("reading_level_label", "Standard")),
            word_count=int(raw_scores.get("word_count", 0)),
            sentence_count=int(raw_scores.get("sentence_count", 0)),
        )

        metadata_entity = RFPMetadata(
            id=uuid4(),
            ticket_id=tid,
            client_name=meta_dict.get("client_name", "Empresa"),
            client_country=meta_dict.get("client_country", "ES"),
            currency=meta_dict.get("currency", "EUR"),
            services_requested=meta_dict.get("services_requested", []),
            monthly_volume=meta_dict.get("monthly_volume"),
            deadline=meta_dict.get("deadline"),
            budget_range=meta_dict.get("budget_range"),
            departments_needed=meta_dict.get("departments_needed", []),
            unsupported_services=meta_dict.get("unsupported_services", []),
            readability_scores=scores,
        )

        # Retrieve saved sections from repository if present, otherwise rebuild from state
        if self.repository:
            sections = self.repository.list_department_sections(tid)
        else:
            sections = []
            for d_id, s_dict in state.get("department_sections", {}).items():
                sections.append(
                    DepartmentSection(
                        id=uuid4(),
                        ticket_id=tid,
                        department_id=s_dict["department_id"],
                        department_name=s_dict["department_name"],
                        responsible_person=s_dict["responsible_person"],
                        key_aspects=s_dict["key_aspects"],
                        open_questions=s_dict["open_questions"],
                        policy_warnings=s_dict["policy_warnings"],
                    )
                )

        handoff_entity = self.synthesizer.synthesize(
            ticket_id=tid,
            metadata=metadata_entity,
            sections=sections,
            markdown_content=state["markdown_content"],
        )

        if self.repository:
            self.repository.save_handoff_payload(handoff_entity)
            ticket = self.repository.get_ticket(tid)
            if ticket:
                ticket.mark_complete()
                self.repository.save_ticket(ticket)

        return {
            "synthesis": handoff_entity.full_handoff_json["sales_synthesis"],
            "status": TicketStatus.ANALISIS_COMPLETO.value,
        }

    def execute(self, ticket_id: UUID, pdf_path: str) -> RFPState:
        """Run the full intake graph synchronously."""
        initial_state = create_initial_state(ticket_id, pdf_path)
        return self.graph.invoke(initial_state)


def run_rfp_pipeline_background(ticket_id: UUID, pdf_path: str) -> None:
    """Entry point for FastAPI BackgroundTasks.

    Guarantees no orphaned tickets in 'analizando' state by catching any unhandled exception.
    """
    engine = get_engine()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        pipeline = RFPIntakePipeline(repository=repo)
        try:
            pipeline.execute(ticket_id, pdf_path)
        except Exception as exc:
            logger.exception("RFP intake background execution failed for ticket %s: %s", ticket_id, exc)
            ticket = repo.get_ticket(ticket_id)
            if ticket:
                ticket.mark_discarded(
                    rejection_reason="Error durante el procesamiento del documento.",
                    error_message=f"Pipeline error: {str(exc)}",
                )
                repo.save_ticket(ticket)
