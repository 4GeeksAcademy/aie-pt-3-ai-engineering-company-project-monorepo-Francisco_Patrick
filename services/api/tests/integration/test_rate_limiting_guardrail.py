"""Integration tests for LLM endpoint rate limiting and denial-of-wallet defense (Scenario 5, FR-010, SC-005).

Verifies that:
1. Requests 1 through 30 succeed within rate quota.
2. Request 31 triggers HTTP 429 (Too Many Requests) with a valid Retry-After header.
3. Downstream LLM invocation count remains bounded at 30.
"""

from unittest.mock import MagicMock
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
import pytest

from presentation.dependencies import LLMRateLimiter, verify_llm_rate_limit


@pytest.fixture
def rate_limiting_app():
    """Create test application with an isolated rate limiter instance (30 req quota)."""
    limiter = LLMRateLimiter(max_requests=30, window_seconds=60)
    mock_downstream = MagicMock(return_value={"status": "ok", "tokens_consumed": 150})

    app = FastAPI()

    def test_verify_rate_limit(request=None):
        limiter.check_rate_limit("test_client_session_1")

    @app.post("/api/v1/agent/query")
    async def query_endpoint(_rate: None = Depends(test_verify_rate_limit)):
        return mock_downstream()

    client = TestClient(app)
    return client, mock_downstream, limiter


def test_rate_limiting_guardrail_enforces_http_429(rate_limiting_app) -> None:
    """Verify that requests 1 through 30 return HTTP 200, and request 31 returns HTTP 429 with Retry-After header."""
    client, mock_downstream, _ = rate_limiting_app

    # Execute 30 valid requests within rate quota
    for i in range(1, 31):
        resp = client.post("/api/v1/agent/query", json={"query": f"Inquiry #{i}"})
        assert resp.status_code == status.HTTP_200_OK, f"Request {i} failed with {resp.status_code}"

    assert mock_downstream.call_count == 30

    # 31st request exceeds rate limit -> Must trigger HTTP 429
    resp_31 = client.post("/api/v1/agent/query", json={"query": "Inquiry #31 - Excess"})
    assert resp_31.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in resp_31.headers
    retry_after = int(resp_31.headers["Retry-After"])
    assert retry_after >= 1
    assert "LLM query rate limit exceeded" in resp_31.text

    # Downstream LLM call count MUST remain capped at 30
    assert mock_downstream.call_count == 30


def test_rate_limiter_resets_history(rate_limiting_app) -> None:
    """Verify that resetting rate limiter restores access."""
    client, mock_downstream, limiter = rate_limiting_app

    # Fill quota
    for _ in range(30):
        client.post("/api/v1/agent/query", json={"query": "test"})

    # Ensure blocked
    blocked = client.post("/api/v1/agent/query", json={"query": "test"})
    assert blocked.status_code == 429

    # Reset
    limiter.reset()

    # Now request succeeds
    allowed = client.post("/api/v1/agent/query", json={"query": "test"})
    assert allowed.status_code == 200
