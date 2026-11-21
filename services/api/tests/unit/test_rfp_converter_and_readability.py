"""Unit tests for PDF to Markdown converter and Textstat readability metrics adapters."""

import os
from pathlib import Path
import pytest

from domain.rfp.exceptions import DocumentParseError
from infrastructure.adapters.pdf_to_markdown_adapter import PdfToMarkdownAdapter
from infrastructure.adapters.textstat_readability import TextstatReadabilityAdapter

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_PDF_1 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"
SAMPLE_PDF_3 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-3.pdf"


def test_pdf_to_markdown_conversion_success():
    """Verify that a valid PDF proposal extracts into structured Markdown."""
    assert SAMPLE_PDF_1.is_file(), f"Expected test PDF at {SAMPLE_PDF_1}"
    adapter = PdfToMarkdownAdapter()

    markdown = adapter.convert_to_markdown(str(SAMPLE_PDF_1))

    assert isinstance(markdown, str)
    assert len(markdown) > 50
    assert "# Document: trackflow-request-1.pdf" in markdown
    assert "## Page 1" in markdown
    assert "ModaViva" in markdown


def test_pdf_to_markdown_nonexistent_file_raises_error():
    """Verify that a non-existent file path raises DocumentParseError."""
    adapter = PdfToMarkdownAdapter()

    with pytest.raises(DocumentParseError) as exc_info:
        adapter.convert_to_markdown("non_existent_file_12345.pdf")

    assert "does not exist" in str(exc_info.value)


def test_pdf_to_markdown_empty_file_raises_error(tmp_path):
    """Verify that an empty file raises DocumentParseError."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    adapter = PdfToMarkdownAdapter()
    with pytest.raises(DocumentParseError) as exc_info:
        adapter.convert_to_markdown(str(empty_file))

    assert "is empty" in str(exc_info.value)


def test_textstat_readability_metrics_calculation():
    """Verify readability metrics calculation on sample proposal text."""
    adapter = TextstatReadabilityAdapter()
    sample_text = (
        "TrackFlow provides warehousing and order fulfillment services for online stores. "
        "We ship goods to customers quickly and safely. "
        "We also handle returns and package inspection."
    )

    scores = adapter.calculate_scores(sample_text)

    assert isinstance(scores.flesch_reading_ease, float)
    assert scores.flesch_reading_ease > 0
    assert scores.flesch_kincaid_grade > 0
    assert isinstance(scores.reading_level_label, str)
    assert scores.word_count > 15
    assert scores.sentence_count >= 3


def test_textstat_readability_metrics_empty_text():
    """Verify safe fallback on empty or whitespace-only text."""
    adapter = TextstatReadabilityAdapter()

    scores = adapter.calculate_scores("   ")

    assert scores.flesch_reading_ease == 0.0
    assert scores.flesch_kincaid_grade == 0.0
    assert scores.reading_level_label == "Unknown"
    assert scores.word_count == 0
    assert scores.sentence_count == 0
