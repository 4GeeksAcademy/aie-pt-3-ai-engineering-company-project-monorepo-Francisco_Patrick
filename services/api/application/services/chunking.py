"""Semantic Markdown chunker for the TrackFlow Knowledge Base.

Implements rule-based semantic chunking that preserves dependent clauses,
bulleted/numbered lists, rate schedules, and Markdown tables while guaranteeing
at least 3 atomic chunks per canonical document and deterministic UUID v5 IDs.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from domain.knowledge.entities import (
    KnowledgeChunk,
    KnowledgeDocument,
    generate_chunk_id,
)
from domain.knowledge.exceptions import IngestionException


CANONICAL_DOCUMENTS: Dict[str, str] = {
    "trackflow-sla-delivery.en.md": "sla-delivery",
    "trackflow-returns-policy.en.md": "returns-policy",
    "trackflow-carrier-coverage.en.md": "carrier-coverage",
    "trackflow-storage-pricing.en.md": "storage-pricing",
}


class MarkdownSemanticChunker:
    """Rule-based semantic chunker for corporate policy Markdown documents."""

    def parse_document(
        self,
        file_path: str | Path,
        doc_id: Optional[str] = None,
        language: str = "en",
        version: str = "1.0.0",
    ) -> KnowledgeDocument:
        """Load and parse a Markdown policy file into a KnowledgeDocument entity.

        Args:
            file_path: Path to the markdown source file.
            doc_id: Optional canonical slug override (e.g. "sla-delivery").
            language: ISO 639-1 language code.
            version: Document version string.

        Returns:
            Parsed KnowledgeDocument domain entity.

        Raises:
            IngestionException: If the file does not exist or is empty.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise IngestionException(f"Knowledge document file not found: {file_path}")

        raw_content = path.read_text(encoding="utf-8").strip()
        if not raw_content:
            raise IngestionException(f"Knowledge document is empty: {file_path}")

        filename = path.name
        resolved_id = doc_id or CANONICAL_DOCUMENTS.get(filename)
        if not resolved_id:
            stem = path.stem.replace(".en", "").replace(".es", "")
            resolved_id = stem.removeprefix("trackflow-")

        title = self._extract_title(raw_content, resolved_id)
        return KnowledgeDocument(
            id=resolved_id,
            title=title,
            source_file=str(path.as_posix()),
            language=language,
            version=version,
            raw_content=raw_content,
        )

    def chunk_document(self, document: KnowledgeDocument) -> List[KnowledgeChunk]:
        """Decompose a KnowledgeDocument into atomic, self-contained KnowledgeChunks.

        Preserves tables, numbered procedures, bullet lists, and dependent clauses.
        Guarantees at least 3 chunks per document with deterministic UUID v5 IDs.

        Args:
            document: Source KnowledgeDocument entity.

        Returns:
            List of KnowledgeChunk entities ordered by chunk_index.

        Raises:
            IngestionException: If document content cannot be chunked into valid segments.
        """
        raw = document.raw_content.strip()
        if not raw:
            raise IngestionException(f"Cannot chunk empty document '{document.id}'.")

        segments = self._extract_semantic_segments(document.id, document.title, raw)
        if len(segments) < 3:
            raise IngestionException(
                f"Document '{document.id}' produced {len(segments)} chunks; at least 3 required."
            )

        chunks: List[KnowledgeChunk] = []
        for idx, (section_title, chunk_text) in enumerate(segments):
            chunk_id = generate_chunk_id(document.id, idx)
            chunks.append(
                KnowledgeChunk(
                    id=chunk_id,
                    company="trackflow",
                    source_document=document.id,
                    section=section_title,
                    language=document.language,
                    chunk_index=idx,
                    text=chunk_text.strip(),
                )
            )
        return chunks

    def load_and_chunk_directory(
        self, directory_path: str | Path
    ) -> Tuple[List[KnowledgeDocument], List[KnowledgeChunk]]:
        """Parse and chunk all canonical markdown files in the knowledge base directory.

        Args:
            directory_path: Directory containing trackflow-*.md files.

        Returns:
            Tuple of (parsed KnowledgeDocuments, all generated KnowledgeChunks).

        Raises:
            IngestionException: If directory is missing or canonical files are absent.
        """
        dir_path = Path(directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            raise IngestionException(f"Knowledge base directory not found: {directory_path}")

        documents: List[KnowledgeDocument] = []
        all_chunks: List[KnowledgeChunk] = []

        for filename, slug in CANONICAL_DOCUMENTS.items():
            file_path = dir_path / filename
            if not file_path.exists():
                raise IngestionException(
                    f"Missing canonical knowledge document '{filename}' in {directory_path}"
                )
            doc = self.parse_document(file_path, doc_id=slug)
            doc_chunks = self.chunk_document(doc)
            documents.append(doc)
            all_chunks.extend(doc_chunks)

        return documents, all_chunks

    def _extract_title(self, raw_content: str, fallback_id: str) -> str:
        """Extract top-level H1 markdown heading or format fallback slug."""
        for line in raw_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.removeprefix("# ").strip()
        return fallback_id.replace("-", " ").title()

    def _extract_semantic_segments(
        self, doc_id: str, doc_title: str, raw_content: str
    ) -> List[Tuple[str, str]]:
        """Split markdown into cohesive (section_title, text) semantic blocks."""
        # Remove top-level H1 header line from body blocks
        lines = raw_content.splitlines()
        body_lines: List[str] = []
        skipped_h1 = False
        for line in lines:
            if not skipped_h1 and line.strip().startswith("# "):
                skipped_h1 = True
                continue
            body_lines.append(line)

        blocks = self._split_into_raw_blocks("\n".join(body_lines))

        # Domain-specific semantic grouping for the 4 canonical TrackFlow documents
        if doc_id == "sla-delivery" and len(blocks) >= 3:
            return self._group_sla_delivery(blocks)
        if doc_id == "returns-policy" and len(blocks) >= 4:
            return self._group_returns_policy(blocks)
        if doc_id == "carrier-coverage" and len(blocks) >= 3:
            return self._group_carrier_coverage(blocks)
        if doc_id == "storage-pricing" and len(blocks) >= 3:
            return self._group_storage_pricing(blocks)

        return self._group_generic_blocks(doc_title, blocks)

    def _split_into_raw_blocks(self, body: str) -> List[str]:
        """Split markdown body on blank lines while keeping intro colons with lists/tables."""
        raw_parts = [part.strip() for part in re.split(r"\n\s*\n", body.strip()) if part.strip()]
        merged: List[str] = []
        i = 0
        while i < len(raw_parts):
            current = raw_parts[i]
            # If current block ends with ':' and next block is a list or table, merge them
            if (
                i + 1 < len(raw_parts)
                and current.endswith(":")
                and self._is_list_or_table(raw_parts[i + 1])
                and not self._is_heading(current)
            ):
                merged.append(f"{current}\n\n{raw_parts[i + 1]}")
                i += 2
            else:
                merged.append(current)
                i += 1
        return merged

    def _is_list_or_table(self, block: str) -> bool:
        """Check whether a markdown block starts with a bullet, number, or table pipe."""
        first_line = block.lstrip().splitlines()[0] if block.strip() else ""
        return bool(
            first_line.startswith("- ")
            or first_line.startswith("* ")
            or first_line.startswith("|")
            or re.match(r"^\d+\.\s", first_line)
        )

    def _is_heading(self, block: str) -> bool:
        """Check whether a block starts with a markdown heading."""
        return block.lstrip().startswith("#")

    def _group_sla_delivery(self, blocks: List[str]) -> List[Tuple[str, str]]:
        """Group Delivery SLA blocks into 3 self-contained semantic chunks."""
        return [
            ("Scope & Delivery Service Tiers", blocks[0]),
            ("Monthly SLA Target & Penalty Compensation", blocks[1]),
            ("Peak Season & High-Demand SLA Exclusions", "\n\n".join(blocks[2:])),
        ]

    def _group_returns_policy(self, blocks: List[str]) -> List[Tuple[str, str]]:
        """Group Returns Policy blocks into 3 self-contained semantic chunks."""
        return [
            ("Standard Reverse Logistics Process & Inspection", blocks[0]),
            ("Standard Return Window & Return Shipping Costs", "\n\n".join(blocks[1:3])),
            ("International Returns Exception & Client Brand Rules", "\n\n".join(blocks[3:])),
        ]

    def _group_carrier_coverage(self, blocks: List[str]) -> List[Tuple[str, str]]:
        """Group Carrier Coverage blocks into 3 self-contained semantic chunks."""
        # If first block is short intro ending with ':', attach to US carrier block
        if len(blocks) >= 4 and blocks[0].endswith(":"):
            us_block = f"{blocks[0]}\n\n{blocks[1]}"
            spain_block = blocks[2]
            routing_block = "\n\n".join(blocks[3:])
        else:
            us_block = blocks[0]
            spain_block = blocks[1]
            routing_block = "\n\n".join(blocks[2:])

        return [
            ("United States (Los Angeles) Carrier Coverage", us_block),
            ("Spain (Zaragoza) Carrier Coverage", spain_block),
            ("Automated Carrier Selection & Carlos Vega Exception Protocol", routing_block),
        ]

    def _group_storage_pricing(self, blocks: List[str]) -> List[Tuple[str, str]]:
        """Group Storage Pricing blocks into 3 self-contained semantic chunks."""
        # blocks[0] has intro + 3 bullet points (standard rate, 30-day grace, 180-day surcharge)
        # Split bullet 3 (180 days) to pair with aging report in chunk 1 so all 3 chunks are cohesive
        first_block_lines = blocks[0].splitlines()
        rate_and_grace_lines: List[str] = []
        long_term_lines: List[str] = []
        in_long_term = False

        for line in first_block_lines:
            if "180 days" in line or "long-term inventory" in line.lower():
                in_long_term = True
            if in_long_term:
                long_term_lines.append(line)
            else:
                rate_and_grace_lines.append(line)

        if rate_and_grace_lines and long_term_lines:
            chunk0_text = "\n".join(rate_and_grace_lines).strip()
            long_term_bullet = "\n".join(long_term_lines).strip()
            chunk1_text = f"Long-term storage policy:\n{long_term_bullet}\n\n{blocks[1]}"
            chunk2_text = "\n\n".join(blocks[2:])
        else:
            chunk0_text = blocks[0]
            chunk1_text = blocks[1]
            chunk2_text = "\n\n".join(blocks[2:])

        return [
            ("Standard Storage Rates & 30-Day Grace Period", chunk0_text),
            ("Long-Term Inventory Surcharge (180+ Days) & Aging Reports", chunk1_text),
            ("Volume Storage Discounts (>50 m³) & Miguel Torres Approval", chunk2_text),
        ]

    def _group_generic_blocks(
        self, doc_title: str, blocks: List[str]
    ) -> List[Tuple[str, str]]:
        """Group generic markdown blocks while preserving tables and headings."""
        segments: List[Tuple[str, str]] = []
        current_section = f"{doc_title} - Overview"
        idx = 0
        while idx < len(blocks):
            block = blocks[idx]
            if block.startswith("#"):
                lines = block.splitlines()
                heading = lines[0].lstrip("#").strip()
                rest = "\n".join(lines[1:]).strip()
                current_section = heading
                if rest:
                    segments.append((current_section, rest))
                elif idx + 1 < len(blocks) and not blocks[idx + 1].startswith("#"):
                    segments.append((current_section, blocks[idx + 1]))
                    idx += 1
            else:
                section_name = (
                    current_section
                    if current_section != f"{doc_title} - Overview"
                    else f"{doc_title} - Section {len(segments) + 1}"
                )
                segments.append((section_name, block))
            idx += 1
        return segments
