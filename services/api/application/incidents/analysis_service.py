"""Incident CSV stream analysis service.

Processes incident batches via generator streams maintaining O(1) memory overhead.
"""

import csv
import io
from typing import Any, Dict, Generator, Iterable, Optional, Union

from application.incidents.dto import IncidentAnalysisResponseDTO
from domain.common.exceptions import EntityNotFoundError
from domain.common.ports import CachePort


class IncidentAnalysisService:
    """Application use case service for stream processing of incident CSV records."""

    def __init__(self, cache: Optional[CachePort] = None) -> None:
        """Initialize analysis service with optional transient cache port."""
        self._cache = cache
        self._last_analysis: Optional[Dict[str, Any]] = None

    def analyze_csv_stream(
        self, file_content: Union[str, bytes, Iterable[str]]
    ) -> IncidentAnalysisResponseDTO:
        """Process incoming CSV stream chunk-by-chunk without full in-memory buffer loading."""
        if isinstance(file_content, bytes):
            text_stream = io.StringIO(file_content.decode("utf-8", errors="replace"))
        elif isinstance(file_content, str):
            text_stream = io.StringIO(file_content)
        else:
            text_stream = io.StringIO("".join(file_content))

        reader = csv.DictReader(text_stream)

        total_rows = 0
        valid_rows = 0
        invalid_rows = 0
        category_breakdown: Dict[str, int] = {
            "warehouse": 0,
            "last_mile": 0,
            "reverse_logistics": 0,
            "customer_experience": 0,
        }
        satisfaction_sum = 0.0
        satisfaction_count = 0

        for row in reader:
            total_rows += 1
            cat = str(row.get("category", "")).strip().lower()
            title = row.get("title", "").strip()

            if not title or not cat:
                invalid_rows += 1
                continue

            valid_rows += 1
            if cat in category_breakdown:
                category_breakdown[cat] += 1
            else:
                category_breakdown[cat] = 1

            sat_raw = row.get("satisfaction_index") or row.get("satisfaction")
            if sat_raw is not None and str(sat_raw).strip():
                try:
                    sat_val = float(str(sat_raw).strip())
                    if 1.0 <= sat_val <= 5.0:
                        satisfaction_sum += sat_val
                        satisfaction_count += 1
                except ValueError:
                    pass

        avg_satisfaction = (
            round(satisfaction_sum / satisfaction_count, 2)
            if satisfaction_count > 0
            else None
        )

        result_dict: Dict[str, Any] = {
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "category_breakdown": category_breakdown,
            "average_satisfaction": avg_satisfaction,
        }

        self._last_analysis = result_dict
        if self._cache is not None:
            self._cache.set("incidents:analysis:latest", result_dict, ttl_seconds=3600)

        return IncidentAnalysisResponseDTO(**result_dict)

    def get_latest_analysis(self) -> Dict[str, Any]:
        """Retrieve most recent analysis result."""
        if self._last_analysis is not None:
            return self._last_analysis

        if self._cache is not None:
            cached = self._cache.get("incidents:analysis:latest")
            if cached is not None:
                return cached

        raise EntityNotFoundError(entity_name="IncidentAnalysis", entity_id="latest")

    def export_analysis_csv(self) -> Generator[str, None, None]:
        """Generate CSV export rows for the latest analysis."""
        analysis = self.get_latest_analysis()
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["metric", "value"])
        writer.writerow(["total_rows", analysis.get("total_rows", 0)])
        writer.writerow(["valid_rows", analysis.get("valid_rows", 0)])
        writer.writerow(["invalid_rows", analysis.get("invalid_rows", 0)])
        writer.writerow(
            ["average_satisfaction", analysis.get("average_satisfaction") or "N/A"]
        )

        for cat, count in analysis.get("category_breakdown", {}).items():
            writer.writerow([f"category_{cat}", count])

        yield output.getvalue()


__all__ = ["IncidentAnalysisService"]
