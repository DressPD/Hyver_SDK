"""Shared test fixtures for Hermes SDK tests."""

import pytest

from hermes import HermesSDK


@pytest.fixture
def base_url() -> str:
    return "http://test.hermes.local:8643"


@pytest.fixture
def api_key() -> str:
    return "test-jwt-token-abc123"


@pytest.fixture
def client(base_url: str, api_key: str) -> HermesSDK:
    """Create a HermesSDK client with test credentials."""
    return HermesSDK(api_key=api_key, base_url=base_url, max_retries=0)
