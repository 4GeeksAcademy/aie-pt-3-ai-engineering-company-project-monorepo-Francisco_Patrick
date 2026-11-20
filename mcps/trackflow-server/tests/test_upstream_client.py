"""Unit tests for UpstreamClient timeout configuration and environment variable overrides."""

import os
from unittest import mock

import pytest

from trackflow_server.clients.upstream_client import (
    DEFAULT_UPSTREAM_TIMEOUT_SECONDS,
    UpstreamClient,
)


class TestUpstreamClientTimeout:
    """Verification suite for UpstreamClient configurable timeouts and env variables."""

    def test_default_timeout_is_four_seconds(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            client = UpstreamClient()
            assert client.timeout_seconds == DEFAULT_UPSTREAM_TIMEOUT_SECONDS
            assert client.timeout_seconds == 4.0

    def test_explicit_timeout_seconds_overrides_default_without_four_second_cap(
        self,
    ) -> None:
        client = UpstreamClient(timeout_seconds=12.5)
        assert client.timeout_seconds == 12.5

        client_short = UpstreamClient(timeout_seconds=1.5)
        assert client_short.timeout_seconds == 1.5

    def test_env_var_upstream_timeout_seconds(self) -> None:
        with mock.patch.dict(
            os.environ, {"TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS": "8.5"}, clear=True
        ):
            client = UpstreamClient()
            assert client.timeout_seconds == 8.5

    def test_env_var_http_timeout(self) -> None:
        with mock.patch.dict(
            os.environ, {"TRACKFLOW_HTTP_TIMEOUT": "6.0"}, clear=True
        ):
            client = UpstreamClient()
            assert client.timeout_seconds == 6.0

    def test_invalid_or_negative_timeout_falls_back_to_default(self) -> None:
        with mock.patch.dict(
            os.environ, {"TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS": "not-a-number"}, clear=True
        ):
            client = UpstreamClient()
            assert client.timeout_seconds == DEFAULT_UPSTREAM_TIMEOUT_SECONDS

        client_neg = UpstreamClient(timeout_seconds=-5.0)
        assert client_neg.timeout_seconds == DEFAULT_UPSTREAM_TIMEOUT_SECONDS

        client_zero = UpstreamClient(timeout_seconds=0.0)
        assert client_zero.timeout_seconds == DEFAULT_UPSTREAM_TIMEOUT_SECONDS
