"""Wrapper evaluation agent coordinating readability, relevance, and compliance in services/api."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List, Literal, Optional

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_response_generation.evaluator import (  # noqa: E402
    DepartmentSectionEvaluator,
)
from domain.rfp.entities import EvaluationResult  # noqa: E402


class RFPEvaluatorAgent:
    """Application-layer evaluator agent wrapping the parallel multi-dimensional evaluator engine."""

    def __init__(
        self,
        evaluator: Optional[DepartmentSectionEvaluator] = None,
    ) -> None:
        self.evaluator = evaluator or DepartmentSectionEvaluator()

    def evaluate_section(
        self,
        department_id: Literal["warehouse", "lastmile", "reverse"],
        draft_content: str,
        client_country: str,
        key_aspects: Optional[Dict[str, Any]] = None,
        open_questions: Optional[List[str]] = None,
        iteration: int = 1,
    ) -> EvaluationResult:
        """Evaluate a department draft across Readability, Relevance, and Compliance in parallel."""
        return self.evaluator.evaluate(
            department_id=department_id,
            draft_text=draft_content,
            client_country=client_country,
            key_aspects=key_aspects,
            open_questions=open_questions,
            iteration=iteration,
        )
