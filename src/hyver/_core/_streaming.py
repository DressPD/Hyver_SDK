"""Typed SSE streaming — RESEARCH §4 #6 (DESIGN §5b: in the cutline).

Parses Server-Sent Events framing (data:/event:/ multi-line, `[DONE]`),
yielding decoded JSON payloads. Sync + async with an identical surface. Not
exercised by OneBusAway but part of the §4 quality bar a Stainless-shaped SDK
must ship.
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Generic, Iterator, Optional, TypeVar

import httpx
import pydantic

from ._exceptions import APIResponseValidationError

_T = TypeVar("_T")

__all__ = ["Stream", "AsyncStream", "ServerSentEvent"]


class ServerSentEvent:
    def __init__(
        self, *, event: Optional[str], data: str, id: Optional[str], retry: Optional[int]
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
        self._event: Optional[str] = None
        self._data: list[str] = []
        self._id: Optional[str] = None
        self._retry: Optional[int] = None

    def flush(self) -> Optional[ServerSentEvent]:
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

    def decode(self, line: str) -> Optional[ServerSentEvent]:
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


def _process_event_data(*, data: object, cast_to: type, response: httpx.Response, client: object) -> object:
    try:
        return client._process_response_data(  # type: ignore[attr-defined]
            data=data, cast_to=cast_to, response=response
        )
    except APIResponseValidationError as exc:
        cause = exc.__cause__
        if not isinstance(cause, pydantic.ValidationError) or not any(
            error["type"] == "union_tag_invalid" for error in cause.errors()
        ):
            raise
        return data


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
                yield _process_event_data(  # type: ignore[misc]
                    data=self._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                    client=self._client,
                )
            sse = self._decoder.flush()
            if sse is not None and sse.data.strip() not in ("", "[DONE]"):
                yield _process_event_data(  # type: ignore[misc]
                    data=self._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                    client=self._client,
                )
        finally:
            self._response.close()

    def close(self) -> None:
        self._response.close()

    @staticmethod
    def _normalize_event_data(data: object) -> object:
        """Normalize older servers that use 'type' to the canonical 'event' field."""
        if isinstance(data, dict) and "type" in data and "event" not in data:
            data["event"] = data.pop("type")
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
                yield _process_event_data(  # type: ignore[misc]
                    data=Stream._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                    client=self._client,
                )
            sse = self._decoder.flush()
            if sse is not None and sse.data.strip() not in ("", "[DONE]"):
                yield _process_event_data(  # type: ignore[misc]
                    data=Stream._normalize_event_data(sse.json()),
                    cast_to=self._cast_to,
                    response=self._response,
                    client=self._client,
                )
        finally:
            await self._response.aclose()

    async def close(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> AsyncStream[_T]:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
