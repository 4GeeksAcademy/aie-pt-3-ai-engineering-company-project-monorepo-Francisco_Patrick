"""Incident CSV report service.

Runs the shared CSV analyzer and keeps the latest result in a cache port so the
export endpoint can serve it later, replacing the former module-level global.
"""

import csv
import io
from typing import Any, Callable, Dict, Optional, TextIO

from domain.common.exceptions import EntityNotFoundError
from domain.common.ports import CachePort

LATEST_REPORT_CACHE_KEY = "incidents:report:latest"
LATEST_REPORT_TTL_SECONDS = 3600


class IncidentCsvReportService:
    """Analyze uploaded incident CSV streams and export the latest metrics as CSV."""

    def __init__(
        self,
        cache: CachePort,
        analyzer: Callable[[TextIO], Dict[str, Any]],
    ) -> None:
        """Initialize the service.

        Args:
            cache: Cache port used to retain the latest analysis result.
            analyzer: Callable converting a text stream into the metrics payload.
        """
        self._cache = cache
        self._analyzer = analyzer

    def analyze(self, text_stream: TextIO) -> Dict[str, Any]:
        """Analyze a CSV text stream and remember the result.

        Args:
            text_stream: Decoded CSV content.

        Returns:
            Analysis payload containing a ``metrics`` mapping.

        Raises:
            ValueError: When the analyzer rejects the CSV content.
        """
        results = self._analyzer(text_stream)
        self._cache.set(
            LATEST_REPORT_CACHE_KEY, results, ttl_seconds=LATEST_REPORT_TTL_SECONDS
        )
        return results

    def export_latest_csv(self) -> str:
        """Render the latest analysis metrics as CSV text.

        Returns:
            CSV document with a ``Metric,Value`` header.

        Raises:
            EntityNotFoundError: When no analysis has been performed yet.
        """
        latest: Optional[Dict[str, Any]] = self._cache.get(LATEST_REPORT_CACHE_KEY)
        if not latest:
            raise EntityNotFoundError(message="No previous analysis found to export.")

        metrics = latest["metrics"]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Elements Processed", metrics["total_processed"]])
        writer.writerow(["Valid Records", metrics["valid_records"]])
        writer.writerow(["Invalid Records", metrics["invalid_records"]])
        for category, count in metrics["category_breakdown"].items():
            writer.writerow([f"Category: {category}", count])
        for status, count in metrics["status_breakdown"].items():
            writer.writerow([f"Status: {status}", count])
        writer.writerow(
            ["Average Satisfaction Index", metrics["average_satisfaction_index"]]
        )
        return output.getvalue()


__all__ = ["IncidentCsvReportService", "LATEST_REPORT_CACHE_KEY"]
