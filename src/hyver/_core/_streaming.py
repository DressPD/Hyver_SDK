"""Typed SSE streaming — RESEARCH §4 #6 (DESIGN §5b: in the cutline).

Parses Server-Sent Events framing (data:/event:/ multi-line, `[DONE]`),
yielding decoded JSON payloads. Sync + async with an identical surface. Not
exercised by OneBusAway but part of the §4 quality bar a Stainless-shaped SDK
must ship.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Generic, TypeVar

import httpx

_T = TypeVar("_T")

__all__ = ["Stream", "AsyncStream", "ServerSentEvent"]


class ServerSentEvent:
    def __init__(
        self, *, event: str | None, data: str, id: str | None, retry: int | None
    ) -> None:
        self.event = event
        self.data = data
        self.id = id
        self.retry = retry

    def json(self) -> object:
        return json.loads(self.data)


class _SSEDecoder:
    """Incremental SSE line decoder (handles multi-line `data:` and blanks)."""

    def __init__(self) -> None:
        self._event: str | None = None
        self._data: list[str] = []
        self._id: str | None = None
        self._retry: int | None = None

    def flush(self) -> ServerSentEvent | None:
        if not self._data and self._event is None:
            return None
        sse = ServerSentEvent(
            event=self._event,
            data="\n".join(self._data),
            id=self._id,
            retry=self._retry,
        )
        self._event, self._data, self._id, self._retry = None, [], None, None
        return sse

    def decode(self, line: str) -> ServerSentEvent | None:
        if not line:  # dispatch on blank line
            if not self._data and self._event is None:
                return None
            sse = ServerSentEvent(
                event=self._event,
                data="\n".join(self._data),
                id=self._id,
                retry=self._retry,
            )
            self._event, self._data, self._id, self._retry = None, [], None, None
            return sse
        if line.startswith(":"):
            return None
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            self._event = value
        elif field == "data":
            self._data.append(value)
        elif field == "id":
            self._id = value
        elif field == "retry" and value.isdigit():
            self._retry = int(value)
        return None


class Stream(Generic[_T]):
    def __init__(self, *, cast_to: type, response: httpx.Response, client: object) -> None:
        self._cast_to = cast_to
        self._response = response
        self._client = client
        self._decoder = _SSEDecoder()

    def __iter__(self) -> Iterator[_T]:
        try:
            for line in self._response.iter_lines():
                sse = self._decoder.decode(line.rstrip("\n"))
                if sse is None:
                    continue
                if sse.data.strip() == "[DONE]":
                    break
                yield self._client._process_response_data(  # type: ignore[attr-defined]
                    data=self._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                )
            sse = self._decoder.flush()
            if sse is not None and sse.data.strip() not in ("", "[DONE]"):
                yield self._client._process_response_data(  # type: ignore[attr-defined]
                    data=self._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                )
        finally:
            self._response.close()

    def close(self) -> None:
        self._response.close()

    @staticmethod
    def _normalize_event_data(data: object) -> object:
        """Server sends discriminator as 'event'; Pydantic models use 'type'."""
        if isinstance(data, dict) and "event" in data and "type" not in data:
            data["type"] = data.pop("event")
        return data

    def __enter__(self) -> Stream[_T]:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncStream(Generic[_T]):
    def __init__(self, *, cast_to: type, response: httpx.Response, client: object) -> None:
        self._cast_to = cast_to
        self._response = response
        self._client = client
        self._decoder = _SSEDecoder()

    async def __aiter__(self) -> AsyncIterator[_T]:
        try:
            async for line in self._response.aiter_lines():
                sse = self._decoder.decode(line.rstrip("\n"))
                if sse is None:
                    continue
                if sse.data.strip() == "[DONE]":
                    break
                yield self._client._process_response_data(  # type: ignore[attr-defined]
                    data=Stream._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                )
            sse = self._decoder.flush()
            if sse is not None and sse.data.strip() not in ("", "[DONE]"):
                yield self._client._process_response_data(  # type: ignore[attr-defined]
                    data=Stream._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                )
        finally:
            await self._response.aclose()

    async def close(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> AsyncStream[_T]:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
