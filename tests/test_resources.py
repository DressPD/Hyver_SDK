"""Tests for all Hyver SDK resource endpoints."""

from __future__ import annotations

import json

import httpx
import respx

from hyver import HyverSDK
from hyver.types import (
    ChatCompletionCreateParamsMessages,
    ChatCompletionCreateResponse,
    HealthCheckResponse,
    RunCreateParamsConversationHistory,
    RunCreateParamsImages,
    RunCreateParamsMetadata,
    RunCreateResponse,
)


class TestHealthResource:
    """GET /health"""

    @respx.mock
    def test_health_check(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
        result = client.health.check()
        assert isinstance(result, HealthCheckResponse)
        assert result.status == "healthy"

    @respx.mock
    def test_health_sends_auth_header(self, client: HyverSDK, base_url: str, api_key: str) -> None:
        route = respx.get(f"{base_url}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
        client.health.check()
        assert route.called
        request = route.calls[0].request
        assert request.headers["authorization"] == f"Bearer {api_key}"


class TestCapabilitiesResource:
    """GET /v1/capabilities"""

    @respx.mock
    def test_get_capabilities(self, client: HyverSDK, base_url: str) -> None:
        payload = {"models": ["claude-3"], "tools": ["brave"], "version": "1.0"}
        respx.get(f"{base_url}/v1/capabilities").mock(return_value=httpx.Response(200, json=payload))
        result = client.capabilities.get()
        assert isinstance(result, dict)
        assert result["models"] == ["claude-3"]
        assert result["tools"] == ["brave"]


class TestChatCompletionsResource:
    """POST /v1/chat/completions"""

    @respx.mock
    def test_create_non_streaming(self, client: HyverSDK, base_url: str) -> None:
        payload = {
            "id": "chatcmpl-abc123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "claude-3-sonnet",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        route = respx.post(f"{base_url}/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
        messages = [ChatCompletionCreateParamsMessages(role="user", content="Hi")]
        result = client.chat_completions.create(messages=messages, stream=False)
        assert isinstance(result, ChatCompletionCreateResponse)
        assert result.id == "chatcmpl-abc123"
        assert result.object == "chat.completion"
        assert len(result.choices) == 1
        # Verify request body
        request = route.calls[0].request
        body = json.loads(request.content)
        assert body["messages"] == [{"role": "user", "content": "Hi"}]
        assert body["stream"] is False

    @respx.mock
    def test_create_with_optional_params(self, client: HyverSDK, base_url: str) -> None:
        payload = {
            "id": "chatcmpl-xyz",
            "object": "chat.completion",
            "created": 1700000000,
            "choices": [],
        }
        route = respx.post(f"{base_url}/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
        messages = [ChatCompletionCreateParamsMessages(role="user", content="Hi")]
        client.chat_completions.create(
            messages=messages,
            model="claude-3-opus",
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
            stream=False,
        )
        body = json.loads(route.calls[0].request.content)
        assert body["model"] == "claude-3-opus"
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 100
        assert body["top_p"] == 0.9


class TestRunsResource:
    """POST /v1/runs and POST /v1/runs/{run_id}/stop"""

    @respx.mock
    def test_create_run_minimal(self, client: HyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs").mock(return_value=httpx.Response(200, json={"run_id": "run-abc123"}))
        result = client.runs.create(input="Hello agent", session_id="sess-001")
        assert isinstance(result, RunCreateResponse)
        assert result.run_id == "run-abc123"
        body = json.loads(route.calls[0].request.content)
        assert body["input"] == "Hello agent"
        assert body["session_id"] == "sess-001"

    @respx.mock
    def test_create_run_with_id_field(self, client: HyverSDK, base_url: str) -> None:
        """Backend may return 'id' instead of 'run_id'."""
        respx.post(f"{base_url}/v1/runs").mock(return_value=httpx.Response(200, json={"id": "run-xyz"}))
        result = client.runs.create(input="Test", session_id="sess-002")
        assert result.id == "run-xyz"

    @respx.mock
    def test_create_run_full_params(self, client: HyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs").mock(return_value=httpx.Response(200, json={"run_id": "run-full"}))
        images = [RunCreateParamsImages(base64="abc=", mimeType="image/png")]  # type: ignore[call-arg]
        history = [
            RunCreateParamsConversationHistory(role="user", content="Previous message"),
            RunCreateParamsConversationHistory(role="assistant", content="Previous response"),
        ]
        metadata = RunCreateParamsMetadata(reasoning=True, search_enabled=False, human_control=True)
        client.runs.create(
            input="Analyze this image",
            session_id="sess-003",
            instructions="Be concise",
            images=images,
            conversation_history=history,
            metadata=metadata,
            tools=["brave", "calculator"],
        )
        body = json.loads(route.calls[0].request.content)
        assert body["input"] == "Analyze this image"
        assert body["instructions"] == "Be concise"
        assert len(body["images"]) == 1
        assert body["images"][0]["mimeType"] == "image/png"
        assert len(body["conversation_history"]) == 2
        assert body["metadata"]["reasoning"] is True
        assert body["metadata"]["human_control"] is True
        assert body["tools"] == ["brave", "calculator"]

    @respx.mock
    def test_stop_run(self, client: HyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs/run-abc/stop").mock(return_value=httpx.Response(200, json={}))
        client.runs.stop(run_id="run-abc")
        assert route.called
        assert route.calls[0].request.method == "POST"


class TestRunsApprovalResource:
    """POST /v1/runs/{run_id}/approval"""

    @respx.mock
    def test_submit_approval(self, client: HyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs/run-xyz/approval").mock(return_value=httpx.Response(200, json={}))
        client.runs_approval.submit(run_id="run-xyz", approved=True)
        assert route.called
        body = json.loads(route.calls[0].request.content)
        assert body["approved"] is True

    @respx.mock
    def test_reject_approval(self, client: HyverSDK, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs/run-xyz/approval").mock(return_value=httpx.Response(200, json={}))
        client.runs_approval.submit(run_id="run-xyz", approved=False)
        body = json.loads(route.calls[0].request.content)
        assert body["approved"] is False


class TestRequestMetadata:
    """Auth headers and URL construction."""

    @respx.mock
    def test_bearer_auth_header(self, base_url: str) -> None:
        route = respx.post(f"{base_url}/v1/runs").mock(return_value=httpx.Response(200, json={"run_id": "r1"}))
        client = HyverSDK(api_key="my-jwt-token", base_url=base_url, max_retries=0)
        client.runs.create(input="test", session_id="s1")
        assert route.calls[0].request.headers["authorization"] == "Bearer my-jwt-token"

    @respx.mock
    def test_url_construction(self, base_url: str) -> None:
        route = respx.get(f"{base_url}/v1/capabilities").mock(return_value=httpx.Response(200, json={}))
        client = HyverSDK(api_key="test", base_url=base_url, max_retries=0)
        client.capabilities.get()
        assert str(route.calls[0].request.url) == f"{base_url}/v1/capabilities"
