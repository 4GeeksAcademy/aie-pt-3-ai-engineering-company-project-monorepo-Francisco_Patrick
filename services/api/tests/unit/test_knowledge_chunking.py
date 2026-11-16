"""Unit tests for MarkdownSemanticChunker (T014).

Verifies:
- All 4 canonical TrackFlow documents parse and produce >= 3 chunks each (12 total)
- Deterministic UUID v5 generation across repeated runs
- Dependent clauses, numbered steps, bullet lists, and Markdown tables are never split
- Standardized payload attributes (`company`, `source_document`, `section`, `language`, `chunk_index`, `text`).
"""

from pathlib import Path
import pytest

from application.services.chunking import MarkdownSemanticChunker
from domain.knowledge.entities import KnowledgeDocument, generate_chunk_id
from domain.knowledge.exceptions import IngestionException


REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_BASE_DIR = REPO_ROOT / "docs" / "company-knowledge-base"


class TestMarkdownSemanticChunker:
    """Unit test suite for MarkdownSemanticChunker."""

    def test_load_and_chunk_all_four_canonical_documents(self) -> None:
        """All 4 canonical documents must produce >= 3 chunks each (12 total)."""
        chunker = MarkdownSemanticChunker()
        documents, chunks = chunker.load_and_chunk_directory(KNOWLEDGE_BASE_DIR)

        assert len(documents) == 4
        assert len(chunks) >= 12

        by_doc = {}
        for chunk in chunks:
            by_doc.setdefault(chunk.source_document, []).append(chunk)
            assert chunk.company == "trackflow"
            assert chunk.language == "en"
            assert len(chunk.text.strip()) >= 20
            assert chunk.section != ""

        for expected_slug in (
            "sla-delivery",
            "returns-policy",
            "carrier-coverage",
            "storage-pricing",
        ):
            assert expected_slug in by_doc
            assert len(by_doc[expected_slug]) >= 3

    def test_deterministic_uuid_v5_chunk_ids(self) -> None:
        """Repeated chunking of the same document must yield identical UUID v5 identifiers."""
        chunker = MarkdownSemanticChunker()
        _, first_run = chunker.load_and_chunk_directory(KNOWLEDGE_BASE_DIR)
        _, second_run = chunker.load_and_chunk_directory(KNOWLEDGE_BASE_DIR)

        first_ids = [c.id for c in first_run]
        second_ids = [c.id for c in second_run]
        assert first_ids == second_ids
        assert len(set(first_ids)) == len(first_ids)
        assert first_run[0].id == generate_chunk_id(
            first_run[0].source_document, first_run[0].chunk_index
        )

    def test_preserves_numbered_lists_and_clauses_intact(self) -> None:
        """Returns policy numbered steps 1, 2, and 3 must stay together in Chunk 0."""
        chunker = MarkdownSemanticChunker()
        doc = chunker.parse_document(
            KNOWLEDGE_BASE_DIR / "trackflow-returns-policy.en.md",
            doc_id="returns-policy",
        )
        chunks = chunker.chunk_document(doc)

        step_chunk = chunks[0].text
        assert "1. The end customer requests a return" in step_chunk
        assert "2. TrackFlow automatically generates" in step_chunk
        assert "3. The product arrives at the warehouse" in step_chunk

    def test_preserves_markdown_tables_within_single_chunk(self) -> None:
        """Markdown tables with introductory colon lines must never be split across chunks."""
        chunker = MarkdownSemanticChunker()
        raw_md = (
            "# Custom Rate Schedule\n\n"
            "Zone pricing breakdown table:\n\n"
            "| Zone | Standard | Express |\n"
            "|------|----------|---------|\n"
            "| US   | $18      | $32     |\n"
            "| ES   | €16      | €28     |\n\n"
            "## Customs Rules\n\n"
            "All international shipments require commercial invoices and HS codes.\n\n"
            "## Escalation Policy\n\n"
            "Any exception requires Operations Director sign-off prior to dispatch."
        )
        doc = KnowledgeDocument(
            id="custom-schedule",
            title="Custom Rate Schedule",
            source_file="custom-schedule.md",
            language="en",
            version="1.0.0",
            raw_content=raw_md,
        )
        chunks = chunker.chunk_document(doc)
        assert len(chunks) == 3
        assert "| Zone | Standard | Express |" in chunks[0].text
        assert "| US   | $18      | $32     |" in chunks[0].text
        assert "| ES   | €16      | €28     |" in chunks[0].text

    def test_raises_ingestion_exception_on_missing_file_or_too_few_chunks(
        self,
    ) -> None:
        """Missing files or documents with < 3 chunks must raise IngestionException."""
        chunker = MarkdownSemanticChunker()
        with pytest.raises(IngestionException):
            chunker.parse_document(KNOWLEDGE_BASE_DIR / "nonexistent-file.md")

        too_short_doc = KnowledgeDocument(
            id="short-doc",
            title="Short",
            source_file="short.md",
            language="en",
            version="1.0.0",
            raw_content="# Short\n\nOnly one single paragraph here with enough characters.",
        )
        with pytest.raises(IngestionException):
            chunker.chunk_document(too_short_doc)
