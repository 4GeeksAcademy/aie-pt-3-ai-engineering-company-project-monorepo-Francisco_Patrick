"""Unit tests for knowledge retrieval helper and currency formatting (User Story 1 - T010)."""

from __future__ import annotations

from typing import Any, List
import pytest

from application.agent.rfp_generator_agents import (
    KnowledgeRetrievalHelper,
    format_currency_amount,
    resolve_currency_for_country,
)
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException


class _FailingVectorStore:
    def search(self, *args: Any, **kwargs: Any) -> List[Any]:
        raise KnowledgeBaseUnavailableException("Qdrant offline in unit test")


class _DummyEmbeddingService:
    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 384


def test_currency_resolution_and_formatting_by_country() -> None:
    """Verify strict currency mapping: US -> USD, ES -> EUR."""
    assert resolve_currency_for_country("US") == "USD"
    assert resolve_currency_for_country("ES") == "EUR"
    assert format_currency_amount(18.5, "US") == "$18.50 USD"
    assert format_currency_amount(16.5, "ES") == "16.50 EUR"


def test_knowledge_retrieval_graceful_fallback_when_unconfigured() -> None:
    """Verify KnowledgeRetrievalHelper falls back to briefing standards when no vector store is configured."""
    helper = KnowledgeRetrievalHelper(vector_store=None, embedding_service=None)
    res = helper.retrieve_department_guidelines("warehouse", "pallet storage rates")
    assert res["fallback_used"] is True
    assert res["source"] == "briefing_fallback"
    assert len(res["snippets"]) == 1
    assert "99.2%" in res["snippets"][0]


def test_knowledge_retrieval_graceful_fallback_when_qdrant_raises() -> None:
    """Verify KnowledgeRetrievalHelper degrades gracefully when Qdrant raises an unavailable exception."""
    helper = KnowledgeRetrievalHelper(
        vector_store=_FailingVectorStore(),  # type: ignore[arg-type]
        embedding_service=_DummyEmbeddingService(),  # type: ignore[arg-type]
    )
    res = helper.retrieve_department_guidelines("reverse", "returns processing turnaround")
    assert res["fallback_used"] is True
    assert res["source"] == "briefing_fallback"
    assert "48 to 72 hours" in res["snippets"][0]
