"""Unit tests for Orchestrator Agent metadata extraction and department scoping."""

from pathlib import Path
import pytest

from data.pipelines.rfp_intake.rfp_orchestrator_agent import RFPOrchestratorAgent
from infrastructure.adapters.pdf_to_markdown_adapter import PdfToMarkdownAdapter

REPO_ROOT = Path(__file__).resolve().parents[5]
SAMPLE_PDF_1 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"
SAMPLE_PDF_2 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-2.pdf"


@pytest.fixture
def converter() -> PdfToMarkdownAdapter:
    return PdfToMarkdownAdapter()


@pytest.fixture
def orchestrator() -> RFPOrchestratorAgent:
    return RFPOrchestratorAgent()


def test_orchestrator_scoping_modaviva_spain(converter: PdfToMarkdownAdapter, orchestrator: RFPOrchestratorAgent):
    """Verify ModaViva scoping: Spain (ES), EUR currency, warehouse + reverse (omitting lastmile)."""
    md = converter.convert_to_markdown(str(SAMPLE_PDF_1))
    result = orchestrator.extract(md)

    assert result.client_name == "ModaViva, S.L."
    assert result.client_country == "ES"
    assert result.currency == "EUR"
    # Scoping strictly warehouse and reverse, bypassing lastmile per document
    assert "warehouse" in result.departments_needed
    assert "reverse" in result.departments_needed
    assert "lastmile" not in result.departments_needed


def test_orchestrator_scoping_luna_cosmetics_us(converter: PdfToMarkdownAdapter, orchestrator: RFPOrchestratorAgent):
    """Verify Luna Cosmetics scoping: US, USD currency, 5000 orders/month, warehouse + lastmile."""
    md = converter.convert_to_markdown(str(SAMPLE_PDF_2))
    result = orchestrator.extract(md)

    assert result.client_name == "Luna Cosmetics"
    assert result.client_country == "US"
    assert result.currency == "USD"
    assert result.monthly_volume == 5000
    assert "warehouse" in result.departments_needed
    assert "lastmile" in result.departments_needed


def test_orchestrator_detects_unsupported_services(orchestrator: RFPOrchestratorAgent):
    """Verify detection of unsupported logistics services."""
    text = (
        "# Proposal Request\n\n"
        "Client: PharmaCold\n"
        "We require refrigerated cold storage and customs clearance for overseas products."
    )
    result = orchestrator.extract(text)

    assert any("cold storage" in s.lower() for s in result.unsupported_services)
    assert any("customs clearance" in s.lower() for s in result.unsupported_services)
