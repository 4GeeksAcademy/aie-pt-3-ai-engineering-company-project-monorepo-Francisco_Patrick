"""Integration tests for Knowledge Base FastAPI routes (T020, T024, T028).

Verifies:
- Dual route mounting (`/api/v1/knowledge/query` and `/knowledge/query`)
- Health endpoint (`GET /api/v1/knowledge/health` and `GET /knowledge/health`)
- User Story 1: Standard operational policy queries (30-day return window, $18 LA / €16 Zaragoza storage, SEUR rural Aragón)
- User Story 2: Business guardrails (Miguel Torres >50 m³, Black Friday +40% SLA warning, Sofía Ramos international returns, Carlos Vega carrier exception)
- User Story 3: Out-of-scope refusal (`is_refusal: true`, `sources: []`) for pharmaceutical refrigeration and unmentioned topics
- Validation errors (HTTP 422 on empty/short queries) and HTTP 503 when Qdrant is unavailable.
"""

import os
from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-knowledge-integration-tests")

from main import app  # noqa: E402
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException  # noqa: E402
from presentation.dependencies import get_knowledge_service_dep  # noqa: E402


client = TestClient(app)


class TestKnowledgeRoutesIntegration:
    """End-to-end integration test suite for Knowledge Base API endpoints."""

    def test_health_endpoint_v1_and_legacy_alias(self) -> None:
        """GET /api/v1/knowledge/health and GET /knowledge/health must report 12 indexed points."""
        for path in ("/api/v1/knowledge/health", "/knowledge/health"):
            res = client.get(path)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "healthy"
            assert data["collection_name"] == "trackflow_knowledge"
            assert data["indexed_points_count"] == 12
            assert data["vector_dimensions"] == 384

    def test_us1_standard_return_window_and_shipping_costs(self) -> None:
        """US1 Scenario 1: Return window (30 days) and client brand vs TrackFlow error shipping costs."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "What is TrackFlow's standard return window and who covers return shipping costs?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "30 days" in data["answer"]
        assert "client brand" in data["answer"].lower()
        assert any(s["source_document"] == "returns-policy" for s in data["sources"])

    def test_us1_storage_rates_los_angeles_vs_zaragoza_and_grace_period(self) -> None:
        """US1 Scenario 2: Storage rate 18 USD LA vs 16 EUR Zaragoza and 30-day grace period."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "What is the standard monthly storage rate in Los Angeles versus Zaragoza?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "18 USD" in data["answer"]
        assert "16 EUR" in data["answer"]
        assert "30" in data["answer"]
        assert any(s["source_document"] == "storage-pricing" for s in data["sources"])

    def test_us1_rural_aragon_carrier_coverage_and_legacy_alias(self) -> None:
        """US1 Scenario 3: SEUR for rural Aragón, MRW under 2 kg, and automatic assignment via /knowledge/query."""
        res = client.post(
            "/knowledge/query",
            json={
                "query": "Which carrier is recommended for rural deliveries in Aragón?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "SEUR" in data["answer"]
        assert "MRW" in data["answer"]
        assert "2 kg" in data["answer"]
        assert any(s["source_document"] == "carrier-coverage" for s in data["sources"])

    def test_us2_guardrail_volume_storage_discount_miguel_torres(self) -> None:
        """US2 Scenario 1 (T024): Storage discount for >50 m³ requires Miguel Torres's approval."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "Can we offer a discount on storage fees for a client storing 75 cubic meters?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "50 cubic meters" in data["answer"]
        assert "Miguel Torres" in data["answer"]
        assert "cannot" in data["answer"].lower()
        assert any(s["source_document"] == "storage-pricing" for s in data["sources"])

    def test_us2_guardrail_peak_season_black_friday_sla_warning(self) -> None:
        """US2 Scenario 2 (T024): Peak season SLA is not guaranteed and may extend up to 40%."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "Can we guarantee 90% delivery SLA during Black Friday sales?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "not guarantee" in data["answer"].lower()
        assert "40%" in data["answer"]
        assert "in advance" in data["answer"].lower()
        assert any(s["source_document"] == "sla-delivery" for s in data["sources"])

    def test_us2_guardrail_international_returns_sofia_ramos(self) -> None:
        """US2 Scenario 3 (T024): Cross-border returns require manual handling by Sofía Ramos's team."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "How do we process a return where a product was purchased in the US and returned in Spain?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "Sofía Ramos" in data["answer"]
        assert "manual" in data["answer"].lower()
        assert any(s["source_document"] == "returns-policy" for s in data["sources"])

    def test_us2_guardrail_carrier_override_carlos_vega(self) -> None:
        """US2 Scenario 4 (T024): Manual carrier override requires Carlos Vega's approval."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "Can an account manager manually choose the carrier for a shipment?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "Carlos Vega" in data["answer"]
        assert any(s["source_document"] == "carrier-coverage" for s in data["sources"])

    def test_us3_out_of_scope_query_triggers_refusal(self) -> None:
        """US3 Scenario 1 (T028): Out-of-scope pharmaceutical refrigeration query returns is_refusal=True."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is True
        assert data["sources"] == []
        assert "does not contain" in data["answer"].lower()

    def test_cross_lingual_spanish_long_term_inventory_query(self) -> None:
        """Edge Case: Spanish query on 180-day low-rotation surcharge returns 150% starting day 181."""
        res = client.post(
            "/api/v1/knowledge/query",
            json={
                "query": "¿Cuál es el recargo por inventario de baja rotación después de 180 días?",
                "language": "es",
                "top_k": 3,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_refusal"] is False
        assert "150%" in data["answer"]
        assert "181" in data["answer"]
        assert any(s["source_document"] == "storage-pricing" for s in data["sources"])

    def test_validation_error_on_empty_or_whitespace_query(self) -> None:
        """Empty or whitespace-only queries must be rejected with HTTP 422."""
        res = client.post("/api/v1/knowledge/query", json={"query": "   "})
        assert res.status_code == 422

    def test_service_unavailable_returns_http_503(self) -> None:
        """When Qdrant raises KnowledgeBaseUnavailableException, endpoint must return HTTP 503."""

        class FailingKnowledgeService:
            def query(self, request: object) -> object:
                raise KnowledgeBaseUnavailableException(
                    "Qdrant vector database connection timed out."
                )

        app.dependency_overrides[get_knowledge_service_dep] = (
            lambda: FailingKnowledgeService()
        )
        try:
            res = client.post(
                "/api/v1/knowledge/query",
                json={"query": "What is the standard return window?"},
            )
            assert res.status_code == 503
            body = res.json()
            assert body["error"] == "SERVICE_UNAVAILABLE"
        finally:
            app.dependency_overrides.pop(get_knowledge_service_dep, None)
