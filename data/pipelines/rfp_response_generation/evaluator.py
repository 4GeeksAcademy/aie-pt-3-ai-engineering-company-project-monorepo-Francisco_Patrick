"""Parallel multi-dimensional evaluator engine for Part 2 department proposal sections.

Evaluates generated section drafts concurrently across three dimensions:
1. Readability: Flesch Reading Ease via textstat.
2. Relevance: Coverage of Part 1 department key_aspects.
3. Compliance: Deterministic verification of the 5 TrackFlow briefing rules (§5).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Literal, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import textstat  # noqa: E402

from data.pipelines.rfp_response_generation.compliance_rules import (  # noqa: E402
    evaluate_compliance_rules,
)
from domain.rfp.entities import (  # noqa: E402
    ComplianceEvaluation,
    EvaluationResult,
    ReadabilityEvaluation,
    RelevanceEvaluation,
)

# Mapping of Part 1 key_aspect keys to semantic keywords expected in the draft
ASPECT_KEYWORDS_MAP: Dict[str, List[str]] = {
    "warehouse_location_preference": [
        "location",
        "ubicación",
        "centro",
        "facility",
        "zaragoza",
        "los ángeles",
        "los angeles",
        "hub",
        "warehouse",
        "almacén",
    ],
    "pallet_storage_required": [
        "pallet",
        "palet",
        "storage",
        "almacenamiento",
        "posiciones",
        "capacity",
        "capacidad",
    ],
    "sku_count": [
        "sku",
        "referencias",
        "catalog",
        "catálogo",
        "inventory",
        "inventario",
    ],
    "special_handling": [
        "handling",
        "manipulación",
        "especial",
        "special",
        "fragile",
        "cosmetics",
        "fashion",
        "standard",
        "estándar",
    ],
    "onboarding_complexity": [
        "onboarding",
        "integración",
        "implementación",
        "transition",
        "transición",
        "schedule",
        "cronograma",
    ],
    "carrier_strategy": [
        "carrier",
        "transportista",
        "network",
        "red",
        "shipping",
        "envío",
        "last mile",
        "última milla",
    ],
    "geographic_scope": [
        "geographic",
        "geográfico",
        "coverage",
        "cobertura",
        "domestic",
        "nacional",
        "scope",
        "alcance",
    ],
    "delivery_sla_requested": [
        "sla",
        "delivery",
        "entrega",
        "transit",
        "tránsito",
        "plazo",
        "on-time",
    ],
    "special_delivery_requirements": [
        "delivery requirement",
        "requisitos de entrega",
        "tracking",
        "seguimiento",
        "signature",
        "firma",
        "standard delivery",
        "entrega estándar",
    ],
    "return_window_days": [
        "window",
        "ventana",
        "plazo de devolución",
        "return period",
        "days",
        "días",
    ],
    "estimated_return_rate": [
        "return rate",
        "tasa de devolución",
        "tasa estimada",
        "volumen de devoluciones",
        "returns volume",
    ],
    "inspection_required": [
        "inspection",
        "inspección",
        "quality check",
        "control de calidad",
        "grading",
    ],
    "disposition_flow": [
        "disposition",
        "disposición",
        "reventa",
        "restock",
        "reacondicionamiento",
        "refurbish",
        "descarte",
    ],
}


def _clean_markdown_for_readability(markdown_text: str) -> str:
    """Normalize Markdown formatting so textstat evaluates prose sentences accurately."""
    lines = (markdown_text or "").splitlines()
    prose_lines: List[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        # Skip markdown table separator rows like |---|---|
        if re.match(r"^\|?[\s\-:|]+\|?$", line):
            continue
        # Skip pure markdown table rows so numeric cells don't skew sentence length
        if line.startswith("|") and line.endswith("|"):
            continue
        # Strip heading hashes and bullet markers
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        if line and line[-1] not in ".!?":
            line = line + "."
        prose_lines.append(line)
    return " ".join(prose_lines)


def evaluate_readability(
    draft_text: str,
    min_score: float = 30.0,
    max_score: float = 95.0,
    min_word_count: int = 25,
) -> ReadabilityEvaluation:
    """Compute Flesch Reading Ease score and evaluate against business readability thresholds.

    Args:
        draft_text: Generated Markdown proposal section draft.
        min_score: Minimum acceptable Flesch Reading Ease score (default 30.0).
        max_score: Maximum acceptable Flesch Reading Ease score (default 95.0).
        min_word_count: Minimum word count for a substantive proposal section.

    Returns:
        ReadabilityEvaluation with pass_status, score, and diagnostic details.
    """
    raw = (draft_text or "").strip()
    if not raw:
        return ReadabilityEvaluation(
            pass_status=False,
            score=0.0,
            details="Draft content is empty.",
        )

    prose = _clean_markdown_for_readability(raw)
    word_count = int(textstat.lexicon_count(raw, removepunct=True))
    if word_count < min_word_count:
        score = float(textstat.flesch_reading_ease(prose or raw))
        return ReadabilityEvaluation(
            pass_status=False,
            score=round(score, 2),
            details=(
                f"Draft is too brief ({word_count} words < {min_word_count} minimum required "
                f"for an executive proposal section)."
            ),
        )

    score = round(float(textstat.flesch_reading_ease(prose or raw)), 2)
    grade = round(float(textstat.flesch_kincaid_grade(prose or raw)), 2)

    if score < min_score:
        return ReadabilityEvaluation(
            pass_status=False,
            score=score,
            details=(
                f"Readability score {score} is below minimum threshold {min_score} "
                f"(Grade level {grade}). Simplify overly complex sentences."
            ),
        )
    if score > max_score:
        return ReadabilityEvaluation(
            pass_status=False,
            score=score,
            details=(
                f"Readability score {score} exceeds maximum threshold {max_score} "
                f"(Grade level {grade}). Use professional executive business tone."
            ),
        )

    return ReadabilityEvaluation(
        pass_status=True,
        score=score,
        details=f"Flesch Reading Ease {score} (FK Grade {grade}, {word_count} words) meets executive standard.",
    )


def evaluate_relevance(
    draft_text: str,
    key_aspects: Optional[Dict[str, Any]] = None,
    open_questions: Optional[List[str]] = None,
) -> RelevanceEvaluation:
    """Verify that all required Part 1 department key_aspects are addressed in the draft.

    Args:
        draft_text: Generated Markdown proposal section draft.
        key_aspects: Dictionary of operational parameters extracted in Part 1.
        open_questions: Optional list of open questions from Part 1.

    Returns:
        RelevanceEvaluation with pass_status and list of any missing_aspects.
    """
    text = (draft_text or "").lower()
    aspects = key_aspects or {}
    missing: List[str] = []

    if not text.strip():
        return RelevanceEvaluation(
            pass_status=False,
            missing_aspects=list(aspects.keys()) if aspects else ["draft_content"],
        )

    for aspect_key, aspect_val in aspects.items():
        # Determine keywords associated with this aspect key
        candidate_keywords = list(ASPECT_KEYWORDS_MAP.get(aspect_key, []))
        # Also include normalized words from the aspect key name itself
        key_tokens = [tok for tok in aspect_key.lower().split("_") if len(tok) > 2]
        candidate_keywords.extend(key_tokens)

        # Also check if the specific value (when non-empty string/number) appears in the text
        val_matched = False
        if aspect_val is not None:
            if isinstance(aspect_val, (str, int, float)) and not isinstance(aspect_val, bool):
                val_str = str(aspect_val).lower().strip()
                if val_str and val_str in text:
                    val_matched = True
            elif isinstance(aspect_val, list) and aspect_val:
                if any(str(item).lower() in text for item in aspect_val):
                    val_matched = True

        keyword_matched = any(kw.lower() in text for kw in candidate_keywords)
        if not (val_matched or keyword_matched):
            missing.append(aspect_key)

    # If open_questions exist, verify the draft includes a section or mention of open questions / assumptions
    if open_questions:
        has_question_acknowledgment = any(
            kw in text
            for kw in [
                "open question",
                "preguntas abiertas",
                "confirmación",
                "pending confirmation",
                "to be confirmed",
                "a confirmar",
                "supuestos",
                "assumptions",
                "onboarding",
                "sku",
                "pallet",
                "sla",
                "tasa",
            ]
        )
        if not has_question_acknowledgment:
            missing.append("open_questions_coverage")

    return RelevanceEvaluation(
        pass_status=len(missing) == 0,
        missing_aspects=missing,
    )


def build_feedback_for_generator(
    readability: ReadabilityEvaluation,
    relevance: RelevanceEvaluation,
    compliance: ComplianceEvaluation,
) -> str:
    """Compile actionable revision instructions prioritizing compliance > relevance > readability."""
    if readability.pass_status and relevance.pass_status and compliance.pass_status:
        return "All readability, relevance, and compliance criteria passed. No revisions needed."

    instructions: List[str] = []

    if not compliance.pass_status:
        for violation in compliance.violations:
            instructions.append(f"[COMPLIANCE CRITICAL] {violation}")

    if not relevance.pass_status:
        missing_str = ", ".join(relevance.missing_aspects)
        instructions.append(
            f"[RELEVANCE] Address the following missing Part 1 key aspects in the proposal section: {missing_str}."
        )

    if not readability.pass_status:
        instructions.append(f"[READABILITY] {readability.details}")

    return " ".join(instructions)


class DepartmentSectionEvaluator:
    """Coordinates concurrent multi-dimensional evaluation for a department draft."""

    def __init__(
        self,
        min_readability_score: float = 30.0,
        max_readability_score: float = 95.0,
    ) -> None:
        self.min_readability_score = min_readability_score
        self.max_readability_score = max_readability_score

    def evaluate(
        self,
        department_id: Literal["warehouse", "lastmile", "reverse"],
        draft_text: str,
        client_country: str,
        key_aspects: Optional[Dict[str, Any]] = None,
        open_questions: Optional[List[str]] = None,
        iteration: int = 1,
    ) -> EvaluationResult:
        """Run readability, relevance, and compliance checks concurrently in parallel.

        Args:
            department_id: Active department ('warehouse', 'lastmile', or 'reverse').
            draft_text: Generated Markdown proposal section draft.
            client_country: 'US' or 'ES' from Part 1 metadata.
            key_aspects: Part 1 extracted key_aspects for the department.
            open_questions: Part 1 open_questions for the department.
            iteration: Current attempt iteration number (1..3).

        Returns:
            Immutable EvaluationResult containing all 3 dimensions and feedback_for_generator.
        """
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_readability = executor.submit(
                evaluate_readability,
                draft_text,
                self.min_readability_score,
                self.max_readability_score,
            )
            fut_relevance = executor.submit(
                evaluate_relevance,
                draft_text,
                key_aspects,
                open_questions,
            )
            fut_compliance = executor.submit(
                evaluate_compliance_rules,
                draft_text,
                client_country,
                department_id,
            )

            readability_res = fut_readability.result()
            relevance_res = fut_relevance.result()
            compliance_res = fut_compliance.result()

        overall_pass = (
            readability_res.pass_status
            and relevance_res.pass_status
            and compliance_res.pass_status
        )
        feedback = build_feedback_for_generator(
            readability_res, relevance_res, compliance_res
        )

        return EvaluationResult(
            department_id=department_id,
            iteration=iteration,
            readability=readability_res,
            relevance=relevance_res,
            compliance=compliance_res,
            overall_pass=overall_pass,
            feedback_for_generator=feedback,
            evaluated_at=datetime.now(timezone.utc),
        )
