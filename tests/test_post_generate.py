"""Regression tests for offline post-generation patches."""

from __future__ import annotations

from scripts import post_generate

GENERATED_STREAMING_SOURCE = """from __future__ import annotations

from typing import AsyncIterator, Generic, Iterator, Optional, TypeVar

import httpx

_T = TypeVar("_T")


class ServerSentEvent:
    data: str

    def json(self) -> object:
        return {}


class _SSEDecoder:
    def decode(self, line: str) -> Optional[ServerSentEvent]:
        if not line:  # dispatch on blank line
            return None
        return None


class Stream(Generic[_T]):
    def __init__(self) -> None:
        self._decoder = _SSEDecoder()
        self._response = None
        self._client = None
        self._cast_to = object

    def __iter__(self) -> Iterator[_T]:
        for line in self._response.iter_lines():
            sse = self._decoder.decode(line.rstrip("\\n"))
            if sse is None:
                continue
            if sse.data.strip() == "[DONE]":
                break
            yield self._client._process_response_data(  # type: ignore[attr-defined]
                data=sse.json(), cast_to=self._cast_to, response=self._response
            )

    def close(self) -> None:
        self._response.close()


class AsyncStream(Generic[_T]):
    def __init__(self) -> None:
        self._decoder = _SSEDecoder()
        self._response = None
        self._client = None
        self._cast_to = object

    async def __aiter__(self) -> AsyncIterator[_T]:
        async for line in self._response.aiter_lines():
            sse = self._decoder.decode(line.rstrip("\\n"))
            if sse is None:
                continue
            if sse.data.strip() == "[DONE]":
                break
            yield self._client._process_response_data(  # type: ignore[attr-defined]
                data=sse.json(), cast_to=self._cast_to, response=self._response
            )

    async def close(self) -> None:
        await self._response.aclose()
"""


def test_streaming_post_patch_compiles_generated_source(tmp_path, monkeypatch) -> None:
    core = tmp_path / "_core"
    core.mkdir()
    streaming = core / "_streaming.py"
    streaming.write_text(GENERATED_STREAMING_SOURCE)
    monkeypatch.setattr(post_generate, "SRC", tmp_path)
    monkeypatch.setattr(post_generate, "SDK_ROOT", tmp_path)

    post_generate.patch_streaming_py()
    post_generate.patch_streaming_py()

    patched = streaming.read_text()
    compile(patched, str(streaming), "exec")
    assert "\n    @staticmethod\n    def _normalize_event_data" in patched
    assert patched.count("def _process_event_data(") == 1
    assert patched.count("def __enter__(self) -> Stream[_T]:") == 1
