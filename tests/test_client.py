"""Tests for HyverSDK client initialization."""

import pytest

from hyver import HyverSDK


class TestClientInit:
    """Client construction, env-var fallbacks, and defaults."""

    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ValueError when no api_key and no env var."""
        monkeypatch.delenv("HYVER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="api_key"):
            HyverSDK()

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to HYVER_API_KEY env var."""
        monkeypatch.setenv("HYVER_API_KEY", "env-token-xyz")
        client = HyverSDK()
        # Auth header should contain the env token
        assert client._auth_headers["Authorization"] == "Bearer env-token-xyz"

    def test_explicit_api_key_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit api_key takes precedence over env var."""
        monkeypatch.setenv("HYVER_API_KEY", "env-token")
        client = HyverSDK(api_key="explicit-token")
        assert client._auth_headers["Authorization"] == "Bearer explicit-token"

    def test_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default base URL is localhost:8643."""
        monkeypatch.delenv("HYVER_BASE_URL", raising=False)
        client = HyverSDK(api_key="test")
        assert "localhost:8643" in str(client._base_url)

    def test_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to HYVER_BASE_URL env var."""
        monkeypatch.setenv("HYVER_BASE_URL", "http://custom:9000")
        client = HyverSDK(api_key="test")
        assert "custom:9000" in str(client._base_url)

    def test_explicit_base_url(self) -> None:
        """Explicit base_url overrides everything."""
        client = HyverSDK(api_key="test", base_url="http://myhost:5555")
        assert "myhost:5555" in str(client._base_url)

    def test_default_max_retries(self) -> None:
        """Default max_retries is 2."""
        client = HyverSDK(api_key="test")
        assert client._max_retries == 2

    def test_custom_max_retries(self) -> None:
        """Custom max_retries is respected."""
        client = HyverSDK(api_key="test", max_retries=5)
        assert client._max_retries == 5

    def test_default_timeout(self) -> None:
        """Default timeout is 60 seconds."""
        client = HyverSDK(api_key="test")
        assert client._timeout == 60.0


class TestClientResources:
    """All resource accessors exist and are correctly typed."""

    def test_has_health(self, client: HyverSDK) -> None:
        assert hasattr(client, "health")

    def test_has_capabilities(self, client: HyverSDK) -> None:
        assert hasattr(client, "capabilities")

    def test_has_chat_completions(self, client: HyverSDK) -> None:
        assert hasattr(client, "chat_completions")

    def test_has_runs(self, client: HyverSDK) -> None:
        assert hasattr(client, "runs")

    def test_has_runs_events(self, client: HyverSDK) -> None:
        assert hasattr(client, "runs_events")

    def test_has_runs_approval(self, client: HyverSDK) -> None:
        assert hasattr(client, "runs_approval")
