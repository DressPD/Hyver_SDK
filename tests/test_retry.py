"""Tests for retry logic, timeouts, and connection errors."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from hermes import HermesSDK
from hermes._core._base_client import _INITIAL_RETRY_DELAY, _MAX_RETRY_DELAY
from hermes._core._exceptions import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
)


class TestRetryOnServerError:
    @respx.mock
    def test_retries_on_500(self, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(
            side_effect=[
                httpx.Response(500, json={"error": {"message": "Internal error"}}),
                httpx.Response(200, json={"status": "healthy"}),
            ]
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"):
            result = client.health.check()
        assert result.status == "healthy"
        assert route.call_count == 2

    @respx.mock
    def test_retries_on_429(self, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(
            side_effect=[
                httpx.Response(429, json={"error": {"message": "Rate limited"}}),
                httpx.Response(200, json={"status": "healthy"}),
            ]
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"):
            result = client.health.check()
        assert result.status == "healthy"
        assert route.call_count == 2

    @respx.mock
    def test_exhausts_retries_then_raises(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(500, json={"error": {"message": "Down"}}))
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=2)
        with patch("time.sleep"), pytest.raises(InternalServerError):
            client.health.check()

    @respx.mock
    def test_no_retry_on_400(self, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(
            return_value=httpx.Response(400, json={"error": {"message": "Bad"}})
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=2)
        with pytest.raises(BadRequestError):
            client.health.check()
        assert route.call_count == 1

    @respx.mock
    def test_no_retry_on_401(self, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Unauth"}})
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=2)
        with pytest.raises(AuthenticationError):
            client.health.check()
        assert route.call_count == 1


class TestTimeoutHandling:
    @respx.mock
    def test_timeout_raises_api_timeout_error(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/health").mock(side_effect=httpx.ReadTimeout("read timed out"))
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=0)
        with pytest.raises(APITimeoutError):
            client.health.check()

    @respx.mock
    def test_timeout_retried_then_raises(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/health").mock(side_effect=httpx.ReadTimeout("read timed out"))
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"), pytest.raises(APITimeoutError):
            client.health.check()

    @respx.mock
    def test_timeout_then_success(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/health").mock(
            side_effect=[
                httpx.ReadTimeout("timeout"),
                httpx.Response(200, json={"status": "healthy"}),
            ]
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"):
            result = client.health.check()
        assert result.status == "healthy"


class TestConnectionError:
    @respx.mock
    def test_connection_error_raises(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/health").mock(side_effect=httpx.ConnectError("refused"))
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=0)
        with pytest.raises(APIConnectionError):
            client.health.check()

    @respx.mock
    def test_connection_error_retried(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/health").mock(
            side_effect=[
                httpx.ConnectError("refused"),
                httpx.Response(200, json={"status": "healthy"}),
            ]
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"):
            result = client.health.check()
        assert result.status == "healthy"


class TestRetryDelay:
    def test_retry_after_seconds_header(self, client: HermesSDK) -> None:
        response = httpx.Response(429, headers={"retry-after": "2"})
        delay = client._retry_delay(response, 0)
        assert delay == 2.0

    def test_retry_after_capped_at_max(self, client: HermesSDK) -> None:
        response = httpx.Response(429, headers={"retry-after": "100"})
        delay = client._retry_delay(response, 0)
        assert delay == _MAX_RETRY_DELAY

    def test_exponential_backoff_without_header(self, client: HermesSDK) -> None:
        delay_0 = client._retry_delay(None, 0)
        delay_1 = client._retry_delay(None, 1)
        delay_2 = client._retry_delay(None, 2)
        assert 0 < delay_0 <= _INITIAL_RETRY_DELAY
        assert delay_1 > delay_0 * 0.5
        assert delay_2 <= _MAX_RETRY_DELAY


class TestIdempotencyKeys:
    @respx.mock
    def test_post_gets_idempotency_key_on_retry(self, base_url: str, api_key: str) -> None:
        route = respx.post(f"{base_url}/v1/runs").mock(
            side_effect=[
                httpx.Response(500, json={"error": {"message": "err"}}),
                httpx.Response(200, json={"run_id": "r1"}),
            ]
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"):
            client.runs.create(input="test", session_id="s1")
        retry_request = route.calls[1].request
        assert "idempotency-key" in {k.lower() for k in retry_request.headers}

    @respx.mock
    def test_get_no_idempotency_key(self, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(
            side_effect=[
                httpx.Response(500, json={"error": {"message": "err"}}),
                httpx.Response(200, json={"status": "healthy"}),
            ]
        )
        client = HermesSDK(api_key=api_key, base_url=base_url, max_retries=1)
        with patch("time.sleep"):
            client.health.check()
        retry_request = route.calls[1].request
        assert "idempotency-key" not in {k.lower() for k in retry_request.headers}
