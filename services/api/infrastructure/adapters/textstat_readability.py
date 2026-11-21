"""Textstat adapter for computing document readability and complexity metrics."""

import textstat

from domain.rfp.entities import ReadabilityScores
from domain.rfp.ports import ReadabilityCalculatorPort


class TextstatReadabilityAdapter(ReadabilityCalculatorPort):
    """Adapter computing Flesch Reading Ease and Grade Level via textstat."""

    def calculate_scores(self, text: str) -> ReadabilityScores:
        """Compute readability ease, grade level, and text statistics.

        Args:
            text: Markdown or plain text content.

        Returns:
            ReadabilityScores value object with normalized scores and qualitative label.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return ReadabilityScores(
                flesch_reading_ease=0.0,
                flesch_kincaid_grade=0.0,
                reading_level_label="Unknown",
                word_count=0,
                sentence_count=0,
            )

        try:
            reading_ease = float(textstat.flesch_reading_ease(clean_text))
            grade_level = float(textstat.flesch_kincaid_grade(clean_text))
            word_count = int(textstat.lexicon_count(clean_text, removepunct=True))
            sentence_count = int(textstat.sentence_count(clean_text))
        except Exception:
            # Fallback if text is too minimal or calculation fails
            words = clean_text.split()
            word_count = len(words)
            sentence_count = max(1, clean_text.count(".") + clean_text.count("\n"))
            reading_ease = 50.0
            grade_level = 10.0

        # Qualitative classification based on Flesch Reading Ease standard brackets
        if reading_ease >= 90.0:
            label = "Very Easy"
        elif reading_ease >= 80.0:
            label = "Easy"
        elif reading_ease >= 70.0:
            label = "Fairly Easy"
        elif reading_ease >= 60.0:
            label = "Standard"
        elif reading_ease >= 50.0:
            label = "Fairly Difficult"
        elif reading_ease >= 30.0:
            label = "Difficult"
        else:
            label = "Very Confusing"

        return ReadabilityScores(
            flesch_reading_ease=round(reading_ease, 2),
            flesch_kincaid_grade=round(grade_level, 2),
            reading_level_label=label,
            word_count=word_count,
            sentence_count=sentence_count,
        )
