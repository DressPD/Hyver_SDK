"""Tests for SDK metadata: __version__ export and User-Agent header."""

from __future__ import annotations

from importlib.resources import files

import httpx
import respx

import hyver
from hyver import HyverSDK
from hyver._core._base_client import USER_AGENT


class TestVersion:
    def test_version_exported(self) -> None:
        assert isinstance(hyver.__version__, str)
        assert hyver.__version__  # non-empty

    def test_version_in_all(self) -> None:
        assert "__version__" in hyver.__all__

    def test_pep561_marker_is_packaged(self) -> None:
        assert files("hyver").joinpath("py.typed").is_file()


class TestUserAgent:
    def test_user_agent_format(self) -> None:
        assert USER_AGENT.startswith("hyver-sdk/")
        assert "python/" in USER_AGENT

    @respx.mock
    def test_user_agent_sent(self, client: HyverSDK, base_url: str) -> None:
        route = respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
        client.health.check()
        assert route.calls[0].request.headers["user-agent"] == USER_AGENT

    @respx.mock
    def test_user_agent_overridable(self, client: HyverSDK, base_url: str) -> None:
        route = respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
        client.health.check(extra_headers={"User-Agent": "custom-agent/9.9"})
        assert route.calls[0].request.headers["user-agent"] == "custom-agent/9.9"
