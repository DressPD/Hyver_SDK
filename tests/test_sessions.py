"""Tests for the loader-backed sessions resource."""

from __future__ import annotations

import httpx
import pytest
import respx

from hyver import AsyncHyverSDK, HyverSDK
from hyver.types import Session, SessionHistoryResponse, SessionListResponse

LOADER = "https://loader.test.local/prod"


@pytest.fixture
def client(api_key: str) -> HyverSDK:
    return HyverSDK(api_key=api_key, base_url="http://runtime.local:8643", loader_base_url=LOADER, max_retries=0)


class TestSessionsRouting:
    @respx.mock
    def test_create_targets_loader_host(self, client: HyverSDK, api_key: str) -> None:
        route = respx.post(f"{LOADER}/sessions").mock(
            return_value=httpx.Response(201, json={"sessionId": "s-1", "title": "hi", "status": "active"})
        )
        session = client.sessions.create(title="hi")
        assert isinstance(session, Session)
        assert session.session_id == "s-1"
        req = route.calls[0].request
        assert req.url.host == "loader.test.local"  # routed to loader, not runtime
        assert req.headers["authorization"] == f"Bearer {api_key}"

    @respx.mock
    def test_missing_loader_base_url_raises(self, api_key: str) -> None:
        c = HyverSDK(api_key=api_key, max_retries=0)  # no loader_base_url
        with pytest.raises(ValueError, match="loader base URL"):
            c.sessions.list()

    @respx.mock
    def test_loader_base_url_from_env(self, api_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HYVER_LOADER_BASE_URL", LOADER)
        c = HyverSDK(api_key=api_key, max_retries=0)
        respx.get(f"{LOADER}/sessions").mock(return_value=httpx.Response(200, json={"sessions": []}))
        assert isinstance(c.sessions.list(), SessionListResponse)


class TestSessionsMethods:
    @respx.mock
    def test_list_sends_query_params(self, client: HyverSDK) -> None:
        route = respx.get(f"{LOADER}/sessions").mock(
            return_value=httpx.Response(200, json={"sessions": [{"sessionId": "a"}, {"sessionId": "b"}]})
        )
        result = client.sessions.list(status="active", limit=10)
        assert isinstance(result, SessionListResponse)
        assert [s.session_id for s in result.sessions] == ["a", "b"]
        assert dict(route.calls[0].request.url.params) == {"status": "active", "limit": "10"}

    @respx.mock
    def test_retrieve_url_encodes_id(self, client: HyverSDK) -> None:
        route = respx.get(f"{LOADER}/sessions/a%2Fb").mock(return_value=httpx.Response(200, json={"sessionId": "a/b"}))
        client.sessions.retrieve(session_id="a/b")
        assert route.called

    @respx.mock
    def test_delete_returns_none_on_204(self, client: HyverSDK) -> None:
        respx.delete(f"{LOADER}/sessions/s-1").mock(return_value=httpx.Response(204))
        assert client.sessions.delete(session_id="s-1") is None

    @respx.mock
    def test_history_parses_pagination(self, client: HyverSDK) -> None:
        respx.get(f"{LOADER}/sessions/s-1/history").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sessionId": "s-1",
                    "messages": [{"role": "user", "content": "hi"}],
                    "pagination": {"offset": 0, "limit": 50, "total": 1, "hasMore": False},
                },
            )
        )
        h = client.sessions.history(session_id="s-1", limit=50)
        assert isinstance(h, SessionHistoryResponse)
        assert h.pagination is not None
        assert h.pagination.has_more is False
        assert h.messages[0]["content"] == "hi"


class TestAsyncSessions:
    @respx.mock
    async def test_async_create(self, api_key: str) -> None:
        respx.post(f"{LOADER}/sessions").mock(return_value=httpx.Response(201, json={"sessionId": "s-async"}))
        async with AsyncHyverSDK(api_key=api_key, loader_base_url=LOADER, max_retries=0) as c:
            session = await c.sessions.create(title="x")
            assert session.session_id == "s-async"
