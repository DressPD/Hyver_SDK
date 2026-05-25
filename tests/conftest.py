"""Shared test fixtures for Hermes SDK tests."""

from collections.abc import AsyncGenerator, Generator

import pytest

from hermes import AsyncHermesSDK, HermesSDK


@pytest.fixture
def base_url() -> str:
    return "http://test.hermes.local:8643"


@pytest.fixture
def api_key() -> str:
    return "test-jwt-token-abc123"


@pytest.fixture
def client(base_url: str, api_key: str) -> Generator[HermesSDK, None, None]:
    """Create a HermesSDK client with test credentials."""
    c = HermesSDK(api_key=api_key, base_url=base_url, max_retries=0)
    yield c
    c.close()


@pytest.fixture
async def async_client(base_url: str, api_key: str) -> AsyncGenerator[AsyncHermesSDK, None]:
    """Create an AsyncHermesSDK client with test credentials."""
    c = AsyncHermesSDK(api_key=api_key, base_url=base_url, max_retries=0)
    yield c
    await c.aclose()
