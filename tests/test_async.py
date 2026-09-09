"""Async tests mirroring sync resource tests for AsyncHyverSDK."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from hyver import AsyncHyverSDK
from hyver._core._exceptions import (
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)
from hyver.types import (
    ChatCompletionCreateParamsMessages,
    ChatCompletionCreateResponse,
    HealthCheckResponse,
    RunCreateParamsConversationHistory,
    RunCreateParamsImages,
    RunCreateParamsMetadata,
    RunCreateResponse,
)


class TestAsyncHealthResource:
    @respx.mock
    async def test_health_check(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
        result = await async_client.health.check()
        assert isinstance(result, HealthCheckResponse)
        assert result.status == "healthy"

    @respx.mock
    async def test_sends_auth_header(self, async_client: AsyncHyverSDK, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
        await async_client.health.check()
        assert route.calls[0].request.headers["authorization"] == f"Bearer {api_key}"


class TestAsyncCapabilitiesResource:
    @respx.mock
    async def test_get(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        payload = {"models": ["claude-3"], "tools": ["brave"]}
        respx.get(f"{base_url}/v1/capabilities").mock(return_value=httpx.Response(200, json=payload))
        result = await async_client.capabilities.get()
        assert isinstance(result, dict)
        assert result["models"] == ["claude-3"]


class TestAsyncChatCompletionsResource:
    @respx.mock
    async def test_create_non_streaming(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        payload = {
            "id": "chatcmpl-async",
            "object": "chat.completion",
            "created": 1700000000,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
        }
        route = respx.post(f"{base_url}/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
        messages = [ChatCompletionCreateParamsMessages(role="user", content="Hello")]
        result = await async_client.chat_completions.create(messages=messages, stream=False)
        assert isinstance(result, ChatCompletionCreateResponse)
        assert result.id == "chatcmpl-async"
        body = json.loads(route.calls[0].request.content)
        assert body["messages"] == [{"role": "user", "content": "Hello"}]


class TestAsyncRunsResource:
    @respx.mock
    async def test_create_run(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs").mock(return_value=httpx.Response(200, json={"run_id": "run-async"}))
        result = await async_client.runs.create(input="Test async", session_id="sess-async")
        assert isinstance(result, RunCreateResponse)
        assert result.run_id == "run-async"
        body = json.loads(route.calls[0].request.content)
        assert body["input"] == "Test async"

    @respx.mock
    async def test_create_run_full_params(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs").mock(return_value=httpx.Response(200, json={"run_id": "run-full"}))
        images = [RunCreateParamsImages(base64="abc=", mimeType="image/png")]  # type: ignore[call-arg]
        history = [RunCreateParamsConversationHistory(role="user", content="Prev")]
        metadata = RunCreateParamsMetadata(reasoning=True, search_enabled=False, human_control=True)
        await async_client.runs.create(
            input="Analyze",
            session_id="s1",
            instructions="Be brief",
            images=images,
            conversation_history=history,
            metadata=metadata,
            tools=["brave"],
        )
        body = json.loads(route.calls[0].request.content)
        assert body["instructions"] == "Be brief"
        assert body["metadata"]["reasoning"] is True
        assert body["tools"] == ["brave"]

    @respx.mock
    async def test_stop_run(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs/run-x/stop").mock(return_value=httpx.Response(200, json={}))
        await async_client.runs.stop(run_id="run-x")
        assert route.called


class TestAsyncRunsApprovalResource:
    @respx.mock
    async def test_approve(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs/run-a/approval").mock(return_value=httpx.Response(200, json={}))
        await async_client.runs_approval.submit(run_id="run-a", choice="once")
        body = json.loads(route.calls[0].request.content)
        assert body["choice"] == "once"

    @respx.mock
    async def test_reject(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs/run-a/approval").mock(return_value=httpx.Response(200, json={}))
        await async_client.runs_approval.submit(run_id="run-a", choice="deny")
        body = json.loads(route.calls[0].request.content)
        assert body["choice"] == "deny"


class TestAsyncErrorMapping:
    ERROR_MAP = [
        (400, BadRequestError),
        (401, AuthenticationError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, InternalServerError),
    ]

    @pytest.mark.parametrize("status,exc_cls", ERROR_MAP, ids=[str(s) for s, _ in ERROR_MAP])
    @respx.mock
    async def test_status_to_exception(
        self,
        status: int,
        exc_cls: type,
        async_client: AsyncHyverSDK,
        base_url: str,
    ) -> None:
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(status, json={"error": {"message": "fail"}}))
        with pytest.raises(exc_cls):
            await async_client.health.check()

    @respx.mock
    async def test_error_has_status_code(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/health").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Unauthorized"}})
        )
        with pytest.raises(APIStatusError) as exc_info:
            await async_client.health.check()
        assert exc_info.value.status_code == 401


class TestAsyncContextManager:
    async def test_context_manager(self, base_url: str, api_key: str) -> None:
        client = AsyncHyverSDK(api_key=api_key, base_url=base_url)
        async with client:
            assert hasattr(client, "health")

    async def test_client_resources_exist(self, async_client: AsyncHyverSDK) -> None:
        for attr in ("health", "capabilities", "chat_completions", "runs", "runs_events", "runs_approval"):
            assert hasattr(async_client, attr)
