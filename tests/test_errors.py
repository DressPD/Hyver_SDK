"""Tests for HTTP error → typed exception mapping."""

import httpx
import pytest
import respx

from hyver import HyverSDK
from hyver._core._exceptions import (
    APIError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

ERROR_MAP = [
    (400, BadRequestError),
    (401, AuthenticationError),
    (403, PermissionDeniedError),
    (404, NotFoundError),
    (409, ConflictError),
    (422, UnprocessableEntityError),
    (429, RateLimitError),
    (500, InternalServerError),
    (502, InternalServerError),
    (503, InternalServerError),
]


class TestErrorMapping:
    """HTTP status codes map to correct exception types."""

    @pytest.mark.parametrize("status,exc_cls", ERROR_MAP, ids=[str(s) for s, _ in ERROR_MAP])
    @respx.mock
    def test_status_to_exception(
        self,
        status: int,
        exc_cls: type,
        client: HyverSDK,
        base_url: str,
    ) -> None:
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(status, json={"error": {"message": "fail"}}))
        with pytest.raises(exc_cls):
            client.health.check()

    @respx.mock
    def test_error_has_status_code(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/health").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Unauthorized"}})
        )
        with pytest.raises(APIStatusError) as exc_info:
            client.health.check()
        assert exc_info.value.status_code == 401

    @respx.mock
    def test_error_has_response_object(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(404, json={"error": {"message": "Not found"}}))
        with pytest.raises(APIStatusError) as exc_info:
            client.health.check()
        assert exc_info.value.response is not None
        assert exc_info.value.response.status_code == 404

    @respx.mock
    def test_error_body_parsed(self, client: HyverSDK, base_url: str) -> None:
        error_body = {"error": {"message": "Bad input", "type": "invalid_request", "code": "bad_param"}}
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(400, json=error_body))
        with pytest.raises(BadRequestError) as exc_info:
            client.health.check()
        assert exc_info.value.body is not None


class TestErrorInheritance:
    """Exception hierarchy is correct."""

    def test_status_error_is_api_error(self) -> None:
        assert issubclass(APIStatusError, APIError)

    def test_bad_request_is_status_error(self) -> None:
        assert issubclass(BadRequestError, APIStatusError)

    def test_auth_error_is_status_error(self) -> None:
        assert issubclass(AuthenticationError, APIStatusError)

    def test_rate_limit_is_status_error(self) -> None:
        assert issubclass(RateLimitError, APIStatusError)

    def test_internal_server_is_status_error(self) -> None:
        assert issubclass(InternalServerError, APIStatusError)
