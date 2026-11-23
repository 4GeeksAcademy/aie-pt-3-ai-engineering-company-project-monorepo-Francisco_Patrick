"""Application agent wrapper for deterministic conflict evaluation and arbitration logging (Part 3 of 3).

Wraps `evaluate_and_arbitrate_conflicts` from `data/pipelines/rfp_approval_completion/arbitration.py`
and persists resulting `ArbitrationLog` entries via `IntakeTicketRepositoryPort`.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_approval_completion.arbitration import (  # noqa: E402
    DEFAULT_MAX_REVISIONS,
    evaluate_and_arbitrate_conflicts,
)
from domain.rfp.entities import ArbitrationLog  # noqa: E402
from domain.rfp.ports import IntakeTicketRepositoryPort  # noqa: E402


class RFPArbitrationAgent:
    """Deterministic conflict arbitration agent enforcing TrackFlow briefing §7 rules."""

    def __init__(
        self,
        repository: Optional[IntakeTicketRepositoryPort] = None,
        max_revisions: int = DEFAULT_MAX_REVISIONS,
    ) -> None:
        self.repository = repository
        self.max_revisions = max_revisions

    def evaluate_and_resolve(
        self,
        ticket_id: UUID,
        rfp_metadata: Dict[str, Any],
        department_sections: Dict[str, Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], List[ArbitrationLog]]:
        """Evaluate structured cross-department contradictions, apply briefing rules, and persist logs."""
        updated_meta, updated_sections, logs = evaluate_and_arbitrate_conflicts(
            ticket_id=ticket_id,
            rfp_metadata=rfp_metadata,
            department_sections=department_sections,
            max_revisions=self.max_revisions,
        )

        if self.repository is not None and logs:
            for log_entry in logs:
                self.repository.save_arbitration_log(log_entry)

        return updated_meta, updated_sections, logs
