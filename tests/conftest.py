"""Shared test fixtures for Hyver SDK tests."""

from collections.abc import AsyncGenerator, Generator

import pytest

from hyver import AsyncHyverSDK, HyverSDK


@pytest.fixture
def base_url() -> str:
    return "http://test.hyver.local:8643"


@pytest.fixture
def api_key() -> str:
    return "test-jwt-token-abc123"


@pytest.fixture
def client(base_url: str, api_key: str) -> Generator[HyverSDK, None, None]:
    """Create a HyverSDK client with test credentials."""
    c = HyverSDK(api_key=api_key, base_url=base_url, max_retries=0)
    yield c
    c.close()


@pytest.fixture
async def async_client(base_url: str, api_key: str) -> AsyncGenerator[AsyncHyverSDK, None]:
    """Create an AsyncHyverSDK client with test credentials."""
    c = AsyncHyverSDK(api_key=api_key, base_url=base_url, max_retries=0)
    yield c
    await c.aclose()
