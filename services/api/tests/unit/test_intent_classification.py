"""Unit tests for explicit user intent classification and safe default discard (T016).

Verifies:
- Explicit approval statements in English and Spanish classify as `approve` (confidence >= 0.85).
- Explicit rejection statements classify as `reject`.
- Modification / conditional refinement statements classify as `edit` with `refined_rule` extracted.
- Ambiguous replies ("ok", "maybe later", "I guess") and topic shifts ("Can you check inventory for SKU-401?")
  classify as `unrelated_or_ambiguous` (FR-011, FR-013, SC-003).
- Multi-intent messages ("Yes save that, and what is the current stock of SKU-100?") classify the
  proposal disposition AND extract `residual_query` for same-turn continuation (FR-015).
"""

import pytest

from application.services.memory_service import UserIntentClassifier


class TestUserIntentClassifier:
    """Unit tests for UserIntentClassifier (T016)."""

    def setup_method(self) -> None:
        """Initialize classifier under test."""
        self.classifier = UserIntentClassifier()
        self.sample_proposal = (
            "SEUR no longer covers rural Zaragoza; use local carriers."
        )

    @pytest.mark.parametrize(
        "message",
        [
            "Yes, please remember that rule for SEUR.",
            "Yes, remember this rule",
            "Confirmed, save that to memory.",
            "Sí, guarda esa regla para futuras sesiones.",
            "Sí, recuérdalo por favor.",
            "Approve and save this rule.",
        ],
    )
    def test_classifies_explicit_approval(self, message: str) -> None:
        """Explicit confirmation phrases must classify as 'approve' with high confidence."""
        result = self.classifier.classify(message, self.sample_proposal)
        assert result.intent == "approve"
        assert result.confidence >= 0.85

    @pytest.mark.parametrize(
        "message",
        [
            "No, do not save that.",
            "No, don't remember that rule.",
            "Reject that proposal, do not store it.",
            "No, no guardes eso en memoria.",
            "Discard that, don't save.",
        ],
    )
    def test_classifies_explicit_rejection(self, message: str) -> None:
        """Explicit rejection phrases must classify as 'reject'."""
        result = self.classifier.classify(message, self.sample_proposal)
        assert result.intent == "reject"
        assert result.confidence >= 0.85

    @pytest.mark.parametrize(
        "message,expected_fragment",
        [
            (
                "Remember it, but only for packages over 5kg",
                "only for packages over 5kg",
            ),
            (
                "Save it, except for express air shipments",
                "except for express air shipments",
            ),
            (
                "Guárdalo, pero solo para paquetes de más de 5kg",
                "solo para paquetes de más de 5kg",
            ),
        ],
    )
    def test_classifies_edit_intent_and_extracts_refined_rule(
        self, message: str, expected_fragment: str
    ) -> None:
        """Refinements and conditional modifications must classify as 'edit' with refined_rule populated."""
        result = self.classifier.classify(message, self.sample_proposal)
        assert result.intent == "edit"
        assert result.refined_rule is not None
        assert expected_fragment.lower() in result.refined_rule.lower()

    @pytest.mark.parametrize(
        "message",
        [
            "ok",
            "maybe later",
            "I guess",
            "hmm not sure",
            "Let me think about that for a moment",
            "I will check with my supervisor first",
            "I need to think about whether to save that",
            "Not right now, maybe next week",
            "Déjame pensarlo un momento antes de decidir",
        ],
    )
    def test_ambiguous_non_questions_classify_as_unrelated_with_no_residual_query(
        self, message: str
    ) -> None:
        """12+ char non-question ambiguous remarks must NOT populate residual_query."""
        result = self.classifier.classify(message, self.sample_proposal)
        assert result.intent == "unrelated_or_ambiguous"
        assert result.residual_query is None

    @pytest.mark.parametrize(
        "message",
        [
            "Can you check current stock for SKU-401?",
            "What is the status of ticket INC-001?",
            "What is TrackFlow's standard return window?",
            "Yes, but what about Seville?",
            "Please check current inventory for TF-1001",
        ],
    )
    def test_operational_topic_shifts_classify_as_unrelated_with_residual_query(
        self, message: str
    ) -> None:
        """Genuine operational questions or requests on topic shifts must populate residual_query (FR-013, SC-003)."""
        result = self.classifier.classify(message, self.sample_proposal)
        assert result.intent == "unrelated_or_ambiguous"
        assert result.residual_query == message

    def test_extracts_residual_query_for_multi_intent_turn_continuation(self) -> None:
        """Combined confirmation + operational question must classify disposition and extract residual_query (FR-015)."""
        msg = "Yes save that, and what is the current stock of SKU-100?"
        result = self.classifier.classify(msg, self.sample_proposal)
        assert result.intent == "approve"
        assert result.residual_query is not None
        assert "SKU-100" in result.residual_query

        reject_msg = "No do not save that, and check the status of ticket INC-001."
        reject_result = self.classifier.classify(reject_msg, self.sample_proposal)
        assert reject_result.intent == "reject"
        assert reject_result.residual_query is not None
        assert "INC-001" in reject_result.residual_query
