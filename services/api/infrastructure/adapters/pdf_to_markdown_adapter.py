"""PDF to Markdown converter adapter using pure-Python pypdf text extraction."""

import os
from pathlib import Path
from pypdf import PdfReader

from domain.rfp.exceptions import DocumentParseError
from domain.rfp.ports import DocumentConverterPort


class PdfToMarkdownAdapter(DocumentConverterPort):
    """Adapts PDF document files into structured Markdown text."""

    def convert_to_markdown(self, file_path: str) -> str:
        """Extract text from PDF pages and format as Markdown.

        Args:
            file_path: Path to the target PDF file on disk.

        Returns:
            Extracted text formatted with markdown page separations and headings.

        Raises:
            DocumentParseError: When file does not exist, is empty, or cannot be parsed.
        """
        path = Path(file_path)
        if not path.is_file():
            raise DocumentParseError(f"Target document '{file_path}' does not exist.")

        if path.stat().st_size == 0:
            raise DocumentParseError(f"Target document '{file_path}' is empty.")

        try:
            reader = PdfReader(str(path))
            if len(reader.pages) == 0:
                raise DocumentParseError(f"Target PDF '{file_path}' contains zero pages.")

            md_lines = [f"# Document: {path.name}", ""]
            for idx, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                trimmed = text.strip()
                if trimmed:
                    md_lines.append(f"## Page {idx}")
                    md_lines.append("")
                    md_lines.append(trimmed)
                    md_lines.append("")

            result = "\n".join(md_lines).strip()
            if not result or len(result) < 10:
                raise DocumentParseError(f"Unable to extract readable text from '{file_path}'.")

            return result
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError(f"Error extracting text from PDF '{file_path}': {exc}") from exc
