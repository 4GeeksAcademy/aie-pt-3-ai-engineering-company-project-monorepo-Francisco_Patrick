"""Unit tests for Classifier Agent screening valid RFPs vs non-RFPs."""

from pathlib import Path
import pytest

from data.pipelines.rfp_intake.rfp_classifier_agent import RFPClassifierAgent
from domain.rfp.ports import DocumentConverterPort
from infrastructure.adapters.pdf_to_markdown_adapter import PdfToMarkdownAdapter

REPO_ROOT = Path(__file__).resolve().parents[5]
SAMPLE_PDF_1 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"
SAMPLE_PDF_2 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-2.pdf"
SAMPLE_PDF_3 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-3.pdf"


@pytest.fixture
def converter() -> DocumentConverterPort:
    return PdfToMarkdownAdapter()


@pytest.fixture
def classifier() -> RFPClassifierAgent:
    return RFPClassifierAgent()


def test_classifier_identifies_valid_rfp_modaviva(converter: DocumentConverterPort, classifier: RFPClassifierAgent):
    """Verify that ModaViva RFP (trackflow-request-1.pdf) is classified as a valid RFP."""
    md = converter.convert_to_markdown(str(SAMPLE_PDF_1))
    decision = classifier.classify(md)

    assert decision.is_rfp is True
    assert decision.rejection_reason is None


def test_classifier_identifies_valid_rfp_luna_cosmetics(converter: DocumentConverterPort, classifier: RFPClassifierAgent):
    """Verify that Luna Cosmetics RFP (trackflow-request-2.pdf) is classified as a valid RFP."""
    md = converter.convert_to_markdown(str(SAMPLE_PDF_2))
    decision = classifier.classify(md)

    assert decision.is_rfp is True
    assert decision.rejection_reason is None


def test_classifier_discards_carrier_rate_pitch(converter: DocumentConverterPort, classifier: RFPClassifierAgent):
    """Verify that RapidShip carrier rate pitch (trackflow-request-3.pdf) is discarded as non-RFP."""
    md = converter.convert_to_markdown(str(SAMPLE_PDF_3))
    decision = classifier.classify(md)

    assert decision.is_rfp is False
    assert decision.rejection_reason is not None
    assert len(decision.rejection_reason) > 10
    # Should explain it is a carrier or vendor pitch / sales solicitation
    reason_lower = decision.rejection_reason.lower()
    assert any(term in reason_lower for term in ["carrier", "transportista", "vendor", "pitch", "solicitation", "propuesta comercial", "tarifa"])


def test_classifier_discards_spam_or_irrelevant_text(classifier: RFPClassifierAgent):
    """Verify that irrelevant marketing spam is correctly discarded."""
    spam_text = (
        "# Win a Free Cruise Today!\n\n"
        "Click here to claim your luxury Caribbean holiday. Limited spots available!"
    )
    decision = classifier.classify(spam_text)

    assert decision.is_rfp is False
    assert decision.rejection_reason is not None
