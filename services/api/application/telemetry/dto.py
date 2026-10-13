"""Telemetry application Data Transfer Objects (DTOs)."""

from typing import List
from pydantic import BaseModel, Field

from domain.telemetry.models import IngestReceipt, TelemetryBatch, TelemetryEvent

# Direct aliases of pure domain models for transport serialization
TelemetryEventDTO = TelemetryEvent
TelemetryBatchDTO = TelemetryBatch
IngestReceiptDTO = IngestReceipt

__all__ = ["IngestReceiptDTO", "TelemetryBatchDTO", "TelemetryEventDTO"]
