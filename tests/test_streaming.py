"""Tests for SSE streaming integration — runs_events.stream() and chat_completions.create(stream=True)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
import respx

from hyver import AsyncHyverSDK, HyverSDK
from hyver._core._exceptions import APIResponseValidationError
from hyver._core._streaming import Stream, _SSEDecoder
from hyver.types import (
    ContentDeltaEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ToolStartEvent,
)

SSE_CONTENT_STREAM = (
    'event: response.created\ndata: {"event":"response.created"}\n\n'
    "event: response.output_text.delta\n"
    'data: {"event":"response.output_text.delta","delta":"Hello"}\n\n'
    "event: response.output_text.delta\n"
    'data: {"event":"response.output_text.delta","delta":" world"}\n\n'
    "event: response.completed\n"
    'data: {"event":"response.completed","usage":{"input_tokens":10,'
    '"output_tokens":5,"total_tokens":15},"model":"claude-3","session_id":"s1"}\n\n'
    "data: [DONE]\n\n"
)

SSE_TOOL_STREAM = (
    'event: response.created\ndata: {"event":"response.created"}\n\n'
    "event: tool.start\n"
    'data: {"event":"tool.start","tool":"brave","name":"brave",'
    '"call_id":"call-1","input":{"query":"test"}}\n\n'
    "event: response.output_text.delta\n"
    'data: {"event":"response.output_text.delta","delta":"Result"}\n\n'
    "data: [DONE]\n\n"
)

SSE_STREAM_WITH_UNKNOWN_EVENT = (
    'data: {"event":"response.created"}\n\n'
    'data: {"type":"RUN_STARTED","thread_id":"thread-1"}\n\n'
    'data: {"event":"response.output_text.delta","delta":"still running"}\n\n'
    "data: [DONE]\n\n"
)

SSE_STREAM_WITH_INVALID_KNOWN_EVENT = 'data: {"event":"response.output_text.delta"}\n\n'


class TestSyncRunsEventsStream:
    @respx.mock
    def test_stream_content_events(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-1/events").mock(
            return_value=httpx.Response(200, text=SSE_CONTENT_STREAM, headers={"content-type": "text/event-stream"})
        )
        stream = client.runs_events.stream(run_id="run-1")
        events = list(stream)
        assert len(events) == 4
        assert isinstance(events[0], ResponseCreatedEvent)
        assert isinstance(events[1], ContentDeltaEvent)
        assert events[1].delta == "Hello"
        assert isinstance(events[2], ContentDeltaEvent)
        assert events[2].delta == " world"
        assert isinstance(events[3], ResponseCompletedEvent)
        assert events[3].usage is not None
        assert events[3].usage.total_tokens == 15

    @respx.mock
    def test_stream_tool_events(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-2/events").mock(
            return_value=httpx.Response(200, text=SSE_TOOL_STREAM, headers={"content-type": "text/event-stream"})
        )
        stream = client.runs_events.stream(run_id="run-2")
        events = list(stream)
        assert len(events) == 3
        assert isinstance(events[1], ToolStartEvent)
        assert events[1].tool == "brave"

    @respx.mock
    def test_unknown_event_does_not_terminate_stream(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-unknown/events").mock(
            return_value=httpx.Response(
                200, text=SSE_STREAM_WITH_UNKNOWN_EVENT, headers={"content-type": "text/event-stream"}
            )
        )

        events = list(client.runs_events.stream(run_id="run-unknown"))

        assert isinstance(events[0], ResponseCreatedEvent)
        assert events[1] == {"event": "RUN_STARTED", "thread_id": "thread-1"}
        assert isinstance(events[2], ContentDeltaEvent)

    @respx.mock
    def test_invalid_known_event_still_raises(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-invalid/events").mock(
            return_value=httpx.Response(
                200, text=SSE_STREAM_WITH_INVALID_KNOWN_EVENT, headers={"content-type": "text/event-stream"}
            )
        )

        with pytest.raises(APIResponseValidationError):
            list(client.runs_events.stream(run_id="run-invalid"))

    @respx.mock
    def test_stream_as_context_manager(self, client: HyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-3/events").mock(
            return_value=httpx.Response(200, text=SSE_CONTENT_STREAM, headers={"content-type": "text/event-stream"})
        )
        with client.runs_events.stream(run_id="run-3") as stream:
            events = list(stream)
        assert len(events) == 4

    @respx.mock
    def test_stream_url_encodes_run_id(self, client: HyverSDK, base_url: str) -> None:
        route = respx.get(f"{base_url}/v1/runs/run%2Fslash/events").mock(
            return_value=httpx.Response(200, text="data: [DONE]\n\n", headers={"content-type": "text/event-stream"})
        )
        stream = client.runs_events.stream(run_id="run/slash")
        list(stream)
        assert route.called


class TestAsyncRunsEventsStream:
    @respx.mock
    async def test_stream_content_events(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-1/events").mock(
            return_value=httpx.Response(200, text=SSE_CONTENT_STREAM, headers={"content-type": "text/event-stream"})
        )
        stream = await async_client.runs_events.stream(run_id="run-1")
        events = [e async for e in stream]
        assert len(events) == 4
        assert isinstance(events[1], ContentDeltaEvent)
        assert events[1].delta == "Hello"

    @respx.mock
    async def test_unknown_event_does_not_terminate_stream(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-unknown/events").mock(
            return_value=httpx.Response(
                200, text=SSE_STREAM_WITH_UNKNOWN_EVENT, headers={"content-type": "text/event-stream"}
            )
        )
        stream = await async_client.runs_events.stream(run_id="run-unknown")

        events = [event async for event in stream]

        assert events[1] == {"event": "RUN_STARTED", "thread_id": "thread-1"}
        assert isinstance(events[2], ContentDeltaEvent)

    @respx.mock
    async def test_stream_as_context_manager(self, async_client: AsyncHyverSDK, base_url: str) -> None:
        respx.get(f"{base_url}/v1/runs/run-2/events").mock(
            return_value=httpx.Response(200, text=SSE_CONTENT_STREAM, headers={"content-type": "text/event-stream"})
        )
        stream = await async_client.runs_events.stream(run_id="run-2")
        async with stream:
            events = [e async for e in stream]
        assert len(events) == 4


class TestStreamClosesBehavior:
    def test_stream_closes_response_on_iteration(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.iter_lines.return_value = iter(
            [
                "event: response.created",
                "data: {}",
                "",
                "data: [DONE]",
                "",
            ]
        )
        mock_client = MagicMock()
        mock_client._process_response_data.return_value = {"event": "response.created"}
        stream = Stream(cast_to=dict, response=mock_response, client=mock_client)
        list(stream)
        mock_response.close.assert_called_once()

    def test_stream_closes_on_break(self) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.iter_lines.return_value = iter(
            [
                "event: response.created",
                "data: {}",
                "",
                "event: response.output_text.delta",
                'data: {"delta":"more"}',
                "",
            ]
        )
        mock_client = MagicMock()
        mock_client._process_response_data.return_value = {"event": "test"}
        stream = Stream(cast_to=dict, response=mock_response, client=mock_client)
        for _ in stream:
            break
        mock_response.close.assert_called_once()


class TestSSEDecoderFlush:
    def test_flush_returns_buffered_event(self) -> None:
        decoder = _SSEDecoder()
        decoder.decode("event: test")
        decoder.decode('data: {"key":"val"}')
        sse = decoder.flush()
        assert sse is not None
        assert sse.event == "test"
        assert sse.json() == {"key": "val"}

    def test_flush_returns_none_when_empty(self) -> None:
        decoder = _SSEDecoder()
        assert decoder.flush() is None

    def test_flush_resets_state(self) -> None:
        decoder = _SSEDecoder()
        decoder.decode("data: first")
        decoder.flush()
        assert decoder.flush() is None
