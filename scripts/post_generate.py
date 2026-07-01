"""Post-generation patch script for stainful-generated Hyver SDK.

Run after `make generate` to apply fixes that stainful cannot express.
All patches are idempotent: safe to re-run after any regeneration.
"""

from __future__ import annotations

import sys
from pathlib import Path

SDK_ROOT = Path(__file__).parent.parent
SRC = SDK_ROOT / "src" / "hyver"

_PATCHED_MARKER = "# post_generate patch applied"

_EXIT_CODE = 0


def _patch(path: Path, old: str, new: str, label: str) -> None:
    global _EXIT_CODE
    text = path.read_text()
    if new in text:
        print(f"  [skip]  {label} — already patched")
        return
    if old not in text:
        print(f"  [ERROR] {label} — expected pattern not found in {path.relative_to(SDK_ROOT)}")
        _EXIT_CODE = 1
        return
    path.write_text(text.replace(old, new, 1))
    print(f"  [patch] {label}")


def patch_shared_py() -> None:
    path = SRC / "types" / "shared.py"
    print(f"Patching {path.relative_to(SDK_ROOT)} ...")

    _patch(
        path,
        "    type: Literal['message.delta']\n    delta: str",
        "    type: Literal['response.output_text.delta', 'message.delta']\n    delta: str",
        "Fix 1a: ContentDeltaEvent.type widened",
    )
    _patch(
        path,
        "    type: Literal['hermes.tool.progress']\n    tool:",
        "    type: Literal['tool.progress', 'hermes.tool.progress']\n    tool:",
        "Fix 1b: ToolProgressEvent.type widened",
    )
    _patch(
        path,
        "    type: Literal['hermes.reasoning']\n    text: str",
        "    type: Literal['reasoning.available', 'response.reasoning', 'hermes.reasoning']\n    text: str",
        "Fix 1c: ReasoningEvent.type widened",
    )
    _patch(
        path,
        "    type: Literal['hermes.approval_required']\n    run_id:",
        "    type: Literal['approval.required', 'hermes.approval_required']\n    run_id:",
        "Fix 1d: ApprovalRequiredEvent.type widened",
    )
    _patch(
        path,
        "    type: Literal['message_stop']\n    session_id:",
        "    type: Literal['done', 'message_stop']\n    session_id:",
        "Fix 1e: DoneEvent.type widened",
    )


def patch_base_client_py() -> None:
    path = SRC / "_core" / "_base_client.py"
    print(f"Patching {path.relative_to(SDK_ROOT)} ...")

    _patch(
        path,
        "import random\nimport secrets\nimport time",
        "import email.utils\nimport random\nimport secrets\nimport time",
        "Fix 2/7/9: add email.utils import",
    )

    _patch(
        path,
        "class SyncAPIClient(_BaseClient):\n"
        "    def __init__(self, *, http_client: httpx.Client | None = None, **kw: Any) -> None:\n"
        "        super().__init__(**kw)\n"
        "        self._client = http_client or httpx.Client()\n",
        "class SyncAPIClient(_BaseClient):\n"
        "    def __init__(self, *, http_client: httpx.Client | None = None, **kw: Any) -> None:\n"
        "        super().__init__(**kw)\n"
        "        self._client = http_client or httpx.Client()\n\n"
        "    def close(self) -> None:\n"
        "        self._client.close()\n\n"
        "    def __enter__(self) -> SyncAPIClient:\n"
        "        return self\n\n"
        "    def __exit__(self, *args: Any) -> None:\n"
        "        self.close()\n",
        "Fix 2a: SyncAPIClient.close + context manager",
    )

    _patch(
        path,
        "class AsyncAPIClient(_BaseClient):\n"
        "    def __init__(self, *, http_client: httpx.AsyncClient | None = None,\n"
        "                 **kw: Any) -> None:\n"
        "        super().__init__(**kw)\n"
        "        self._client = http_client or httpx.AsyncClient()\n\n"
        "    async def _request(",
        "class AsyncAPIClient(_BaseClient):\n"
        "    def __init__(self, *, http_client: httpx.AsyncClient | None = None,\n"
        "                 **kw: Any) -> None:\n"
        "        super().__init__(**kw)\n"
        "        self._client = http_client or httpx.AsyncClient()\n\n"
        "    async def aclose(self) -> None:\n"
        "        await self._client.aclose()\n\n"
        "    async def __aenter__(self) -> AsyncAPIClient:\n"
        "        return self\n\n"
        "    async def __aexit__(self, *args: Any) -> None:\n"
        "        await self.aclose()\n\n"
        "    async def _request(",
        "Fix 2b: AsyncAPIClient.aclose + async context manager",
    )

    _patch(
        path,
        "    def _retry_delay(self, response: Optional[httpx.Response], attempt: int) -> float:\n"
        "        if response is not None:\n"
        "            ra = response.headers.get(\"retry-after\")\n"
        "            if ra and ra.isdigit():\n"
        "                return min(float(ra), _MAX_RETRY_DELAY)\n",
        "    def _retry_delay(self, response: Optional[httpx.Response], attempt: int) -> float:\n"
        "        if response is not None:\n"
        "            ra = response.headers.get(\"retry-after\")\n"
        "            if ra:\n"
        "                if ra.isdigit():\n"
        "                    return min(float(ra), _MAX_RETRY_DELAY)\n"
        "                try:\n"
        "                    dt = email.utils.parsedate_to_datetime(ra)\n"
        "                    delta = (dt - dt.now(tz=dt.tzinfo)).total_seconds()\n"
        "                    if delta > 0:\n"
        "                        return min(delta, _MAX_RETRY_DELAY)\n"
        "                except Exception:\n"
        "                    pass\n",
        "Fix 7: Retry-After HTTP-date support",
    )

    _patch(
        path,
        "    def _prepare_retry(self, request: httpx.Request) -> None:\n"
        "        # auto idempotency key so retried writes are safe (RESEARCH §4 #11)\n"
        "        if request.method in (\"POST\", \"PATCH\") and \"idempotency-key\" not in (\n"
        "            k.lower() for k in request.headers\n"
        "        ):\n"
        "            request.headers[\"idempotency-key\"] = f\"stainful-retry-{secrets.token_hex(16)}\"\n",
        "    def _prepare_retry(self, request: httpx.Request, options: Optional[RequestOptions] = None) -> None:\n"
        "        if request.method in (\"POST\", \"PATCH\") and \"idempotency-key\" not in (\n"
        "            k.lower() for k in request.headers\n"
        "        ):\n"
        "            key = (\n"
        "                options.idempotency_key\n"
        "                if options is not None and options.idempotency_key\n"
        "                else f\"stainful-retry-{secrets.token_hex(16)}\"\n"
        "            )\n"
        "            request.headers[\"idempotency-key\"] = key\n",
        "Fix 9a: _prepare_retry honors options.idempotency_key",
    )

    _patch(
        path,
        "        last_exc: Exception | None = None\n"
        "        for attempt in range(self._max_retries + 1):\n"
        "            try:\n"
        "                response = self._client.send(request, stream=stream)\n",
        "        max_retries = (\n"
        "            options.max_retries\n"
        "            if not isinstance(options.max_retries, NotGiven)\n"
        "            else self._max_retries\n"
        "        )\n"
        "        last_exc: Exception | None = None\n"
        "        for attempt in range(max_retries + 1):\n"
        "            try:\n"
        "                response = self._client.send(request, stream=stream)\n",
        "Fix 9b: SyncAPIClient._request honors options.max_retries",
    )

    _patch(
        path,
        "        last_exc: Exception | None = None\n"
        "        for attempt in range(self._max_retries + 1):\n"
        "            try:\n"
        "                response = await self._client.send(request, stream=stream)\n",
        "        max_retries = (\n"
        "            options.max_retries\n"
        "            if not isinstance(options.max_retries, NotGiven)\n"
        "            else self._max_retries\n"
        "        )\n"
        "        last_exc: Exception | None = None\n"
        "        for attempt in range(max_retries + 1):\n"
        "            try:\n"
        "                response = await self._client.send(request, stream=stream)\n",
        "Fix 9c: AsyncAPIClient._request honors options.max_retries",
    )

    for sync_or_async in (
        ("self._max_retries and self._should_retry", "max_retries and self._should_retry"),
        ("attempt < self._max_retries:\n                    time.sleep", "attempt < max_retries:\n                    time.sleep"),
        ("attempt < self._max_retries:\n                    await asyncio.sleep(self._retry_delay(response", "attempt < max_retries:\n                    await asyncio.sleep(self._retry_delay(response"),
        ("attempt < self._max_retries:\n                await asyncio.sleep(self._retry_delay(None", "attempt < max_retries:\n                await asyncio.sleep(self._retry_delay(None"),
        ("attempt < self._max_retries:\n                time.sleep(self._retry_delay(None", "attempt < max_retries:\n                time.sleep(self._retry_delay(None"),
    ):
        old_s, new_s = sync_or_async
        text = path.read_text()
        if old_s in text:
            path.write_text(text.replace(old_s, new_s))

    for old_prepare, new_prepare in (
        ("self._prepare_retry(request)\n                    continue", "self._prepare_retry(request, options)\n                    continue"),
        ("self._prepare_retry(request)\n                continue", "self._prepare_retry(request, options)\n                continue"),
    ):
        text = path.read_text()
        while old_prepare in text:
            path.write_text(text.replace(old_prepare, new_prepare))
            text = path.read_text()


def patch_streaming_py() -> None:
    path = SRC / "_core" / "_streaming.py"
    print(f"Patching {path.relative_to(SDK_ROOT)} ...")

    _patch(
        path,
        "    def decode(self, line: str) -> Optional[ServerSentEvent]:\n"
        "        if not line:  # dispatch on blank line\n",
        "    def flush(self) -> Optional[ServerSentEvent]:\n"
        "        if not self._data and self._event is None:\n"
        "            return None\n"
        "        sse = ServerSentEvent(\n"
        "            event=self._event,\n"
        "            data=\"\\n\".join(self._data),\n"
        "            id=self._id,\n"
        "            retry=self._retry,\n"
        "        )\n"
        "        self._event, self._data, self._id, self._retry = None, [], None, None\n"
        "        return sse\n\n"
        "    def decode(self, line: str) -> Optional[ServerSentEvent]:\n"
        "        if not line:  # dispatch on blank line\n",
        "Fix 3a: _SSEDecoder.flush() method",
    )

    _patch(
        path,
        "    def __iter__(self) -> Iterator[_T]:\n"
        "        for line in self._response.iter_lines():\n"
        "            sse = self._decoder.decode(line.rstrip(\"\\n\"))\n"
        "            if sse is None:\n"
        "                continue\n"
        "            if sse.data.strip() == \"[DONE]\":\n"
        "                break\n"
        "            yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                data=sse.json(), cast_to=self._cast_to, response=self._response\n"
        "            )\n",
        "    def __iter__(self) -> Iterator[_T]:\n"
        "        try:\n"
        "            for line in self._response.iter_lines():\n"
        "                sse = self._decoder.decode(line.rstrip(\"\\n\"))\n"
        "                if sse is None:\n"
        "                    continue\n"
        "                if sse.data.strip() == \"[DONE]\":\n"
        "                    break\n"
        "                yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                    data=self._normalize_event_data(sse.json()),\n"
        "                    cast_to=self._cast_to,\n"
        "                    response=self._response,\n"
        "                )\n"
        "            sse = self._decoder.flush()\n"
        "            if sse is not None and sse.data.strip() not in (\"\", \"[DONE]\"):\n"
        "                yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                    data=self._normalize_event_data(sse.json()),\n"
        "                    cast_to=self._cast_to,\n"
        "                    response=self._response,\n"
        "                )\n"
        "        finally:\n"
        "            self._response.close()\n",
        "Fix 3b: Stream.__iter__ try/finally auto-close + flush + event normalization",
    )

    _patch(
        path,
        "    def close(self) -> None:\n"
        "        self._response.close()\n",
        "    def close(self) -> None:\n"
        "        self._response.close()\n\n"
        "    def __enter__(self) -> Stream[_T]:\n"
        "        return self\n\n"
        "    def __exit__(self, *args: object) -> None:\n"
        "        self.close()\n",
        "Fix 3c: Stream context manager",
    )

    _patch(
        path,
        "    def __enter__(self) -> Stream[_T]:\n",
        "    @staticmethod\n"
        "    def _normalize_event_data(data: object) -> object:\n"
        '        """Server sends discriminator as \'event\'; Pydantic models use \'type\'."""\n'
        "        if isinstance(data, dict) and \"event\" in data and \"type\" not in data:\n"
        "            data[\"type\"] = data.pop(\"event\")\n"
        "        return data\n\n"
        "    def __enter__(self) -> Stream[_T]:\n",
        "Fix 3c2: Stream._normalize_event_data for server event→type mapping",
    )

    _patch(
        path,
        "    async def __aiter__(self) -> AsyncIterator[_T]:\n"
        "        async for line in self._response.aiter_lines():\n"
        "            sse = self._decoder.decode(line.rstrip(\"\\n\"))\n"
        "            if sse is None:\n"
        "                continue\n"
        "            if sse.data.strip() == \"[DONE]\":\n"
        "                break\n"
        "            yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                data=sse.json(), cast_to=self._cast_to, response=self._response\n"
        "            )\n",
        "    async def __aiter__(self) -> AsyncIterator[_T]:\n"
        "        try:\n"
        "            async for line in self._response.aiter_lines():\n"
        "                sse = self._decoder.decode(line.rstrip(\"\\n\"))\n"
        "                if sse is None:\n"
        "                    continue\n"
        "                if sse.data.strip() == \"[DONE]\":\n"
        "                    break\n"
        "                yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                    data=Stream._normalize_event_data(sse.json()),\n"
        "                    cast_to=self._cast_to,\n"
        "                    response=self._response,\n"
        "                )\n"
        "            sse = self._decoder.flush()\n"
        "            if sse is not None and sse.data.strip() not in (\"\", \"[DONE]\"):\n"
        "                yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                    data=Stream._normalize_event_data(sse.json()),\n"
        "                    cast_to=self._cast_to,\n"
        "                    response=self._response,\n"
        "                )\n"
        "        finally:\n"
        "            await self._response.aclose()\n",
        "Fix 3d: AsyncStream.__aiter__ try/finally auto-close + flush + event normalization",
    )

    _patch(
        path,
        "    async def close(self) -> None:\n"
        "        await self._response.aclose()\n",
        "    async def close(self) -> None:\n"
        "        await self._response.aclose()\n\n"
        "    async def __aenter__(self) -> AsyncStream[_T]:\n"
        "        return self\n\n"
        "    async def __aexit__(self, *args: object) -> None:\n"
        "        await self.close()\n",
        "Fix 3e: AsyncStream async context manager",
    )


def patch_params_files() -> None:
    # `Required` and `TypedDict` are imported from typing_extensions (not typing)
    # so the generated params remain importable on Python 3.10, where
    # `typing.Required` does not exist (added in 3.11 per PEP 655).
    typing_import_old = (
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, TypedDict, Union,\n"
        ")"
    )
    typing_import_new = (
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, Union,\n"
        ")\n"
        "from typing_extensions import Required, TypedDict  # noqa: F401"
    )

    chat_path = SRC / "types" / "chat_completions_create_params.py"
    print(f"Patching {chat_path.relative_to(SDK_ROOT)} ...")
    _patch(
        chat_path,
        typing_import_old,
        typing_import_new,
        "Fix 4a: Required/TypedDict from typing_extensions (py3.10 compat)",
    )
    _patch(
        chat_path,
        "    messages: List[ChatCompletionCreateParamsMessages]\n",
        "    messages: Required[List[ChatCompletionCreateParamsMessages]]\n",
        "Fix 4b: messages Required",
    )

    runs_path = SRC / "types" / "runs_create_params.py"
    print(f"Patching {runs_path.relative_to(SDK_ROOT)} ...")
    _patch(
        runs_path,
        typing_import_old,
        typing_import_new,
        "Fix 4c: Required/TypedDict from typing_extensions (py3.10 compat)",
    )
    _patch(
        runs_path,
        "    input: str\n    session_id: str\n",
        "    input: Required[str]\n    session_id: Required[str]\n",
        "Fix 4d: input + session_id Required",
    )

    approval_path = SRC / "types" / "runs_approval_submit_params.py"
    print(f"Patching {approval_path.relative_to(SDK_ROOT)} ...")
    _patch(
        approval_path,
        typing_import_old,
        typing_import_new,
        "Fix 4e: Required/TypedDict from typing_extensions (py3.10 compat)",
    )
    _patch(
        approval_path,
        "    approved: bool\n",
        "    approved: Required[bool]\n",
        "Fix 4f: approved Required",
    )


def patch_runs_create_response_py() -> None:
    path = SRC / "types" / "runs_create_response.py"
    print(f"Patching {path.relative_to(SDK_ROOT)} ...")
    _patch(
        path,
        "from pydantic import Field  # noqa: F401\n",
        "from pydantic import Field, model_validator  # noqa: F401\n",
        "Fix 5a: add model_validator import",
    )
    _patch(
        path,
        "class RunCreateResponse(BaseModel):\n"
        "    run_id: Optional[str] = None\n"
        "    id: Optional[str] = None\n",
        "class RunCreateResponse(BaseModel):\n"
        "    run_id: Optional[str] = None\n"
        "    id: Optional[str] = None\n\n"
        "    @model_validator(mode='after')\n"
        "    def _normalize_run_id(self) -> RunCreateResponse:\n"
        "        if self.run_id is None and self.id is not None:\n"
        "            self.run_id = self.id\n"
        "        return self\n",
        "Fix 5b: model_validator normalizes run_id from id",
    )


def patch_exceptions_py() -> None:
    path = SRC / "_core" / "_exceptions.py"
    print(f"Patching {path.relative_to(SDK_ROOT)} ...")
    _patch(
        path,
        "def status_error_for(response: httpx.Response, body: object | None) -> APIStatusError:\n"
        "    \"\"\"Map an HTTP status to the precise typed exception (RESEARCH §4 #4).\"\"\"\n"
        "    msg = f\"Error code: {response.status_code}\"\n",
        "def status_error_for(response: httpx.Response, body: object | None) -> APIStatusError:\n"
        "    \"\"\"Map an HTTP status to the precise typed exception (RESEARCH §4 #4).\"\"\"\n"
        "    server_msg: Optional[str] = None\n"
        "    if isinstance(body, dict):\n"
        "        err = body.get(\"error\")\n"
        "        if isinstance(err, dict):\n"
        "            server_msg = err.get(\"message\")\n"
        "        if not server_msg:\n"
        "            server_msg = body.get(\"message\")  # type: ignore[assignment]\n"
        "    msg = server_msg or f\"Error code: {response.status_code}\"\n",
        "Fix 6: extract error message from response body",
    )


def patch_missing_bugfixes() -> None:
    client_path = SRC / "_client.py"
    print(f"Patching {client_path.relative_to(SDK_ROOT)} ...")
    _patch(
        client_path,
        '_DEFAULT_BASE_URL = "{base_url}"',
        '_DEFAULT_BASE_URL = "http://localhost:8643"',
        "Fix 10: _client.py default base URL (stainful template → real URL)",
    )

    runs_path = SRC / "resources" / "runs.py"
    print(f"Patching {runs_path.relative_to(SDK_ROOT)} ...")
    _patch(
        runs_path,
        "    def stop(\n"
        "        self,\n"
        "        *,\n"
        "        extra_headers: Headers | None = None,\n",
        "    def stop(\n"
        "        self,\n"
        "        *,\n"
        "        run_id: str,\n"
        "        extra_headers: Headers | None = None,\n",
        "Fix 11a: RunsResource.stop() add missing run_id param",
    )
    _patch(
        runs_path,
        "    async def stop(\n"
        "        self,\n"
        "        *,\n"
        "        extra_headers: Headers | None = None,\n",
        "    async def stop(\n"
        "        self,\n"
        "        *,\n"
        "        run_id: str,\n"
        "        extra_headers: Headers | None = None,\n",
        "Fix 11b: AsyncRunsResource.stop() add missing run_id param",
    )

    approval_path = SRC / "resources" / "runs_approval.py"
    print(f"Patching {approval_path.relative_to(SDK_ROOT)} ...")
    _patch(
        approval_path,
        "    def submit(\n"
        "        self,\n"
        "        *,\n"
        "        approved: bool,\n",
        "    def submit(\n"
        "        self,\n"
        "        *,\n"
        "        run_id: str,\n"
        "        approved: bool,\n",
        "Fix 12a: RunsApprovalResource.submit() add missing run_id param",
    )
    _patch(
        approval_path,
        "    async def submit(\n"
        "        self,\n"
        "        *,\n"
        "        approved: bool,\n",
        "    async def submit(\n"
        "        self,\n"
        "        *,\n"
        "        run_id: str,\n"
        "        approved: bool,\n",
        "Fix 12b: AsyncRunsApprovalResource.submit() add missing run_id param",
    )

    events_path = SRC / "resources" / "runs_events.py"
    print(f"Patching {events_path.relative_to(SDK_ROOT)} ...")
    events_text = events_path.read_text()
    if "self._client._request" in events_text:
        print("  [skip]  Fix 13: runs_events.py full rewrite — already patched")
    else:
        events_path.write_text(
            "# File generated by stainful — DO NOT EDIT"
            " (manual fixes applied for run_id param + SSE streaming).\n"
            "from __future__ import annotations\n"
            "\n"
            "from functools import cached_property\n"
            "from typing import Annotated, Union\n"
            "from urllib.parse import quote\n"
            "\n"
            "import httpx\n"
            "\n"
            "from hyver._core._request_options import make_request_options\n"
            "from hyver._core._resource import AsyncAPIResource, SyncAPIResource\n"
            "from hyver._core._response import (\n"
            "    async_to_raw_response_wrapper,\n"
            "    async_to_streamed_response_wrapper,\n"
            "    to_raw_response_wrapper,\n"
            "    to_streamed_response_wrapper,\n"
            ")\n"
            "from hyver._core._sentinels import NotGiven, not_given\n"
            "from hyver._core._types import Body, Headers, Query\n"
            "from hyver._core._streaming import AsyncStream, Stream\n"
            "from pydantic import Field\n"
            "from hyver.types import (\n"
            "    ApprovalRequiredEvent,\n"
            "    ContentDeltaEvent,\n"
            "    DoneEvent,\n"
            "    ErrorEvent,\n"
            "    OutputItemAddedEvent,\n"
            "    OutputItemDoneEvent,\n"
            "    ReasoningEvent,\n"
            "    ResponseCompletedEvent,\n"
            "    ResponseCreatedEvent,\n"
            "    ResponseFailedEvent,\n"
            "    RunCompletedEvent,\n"
            "    RunFailedEvent,\n"
            "    ToolProgressEvent,\n"
            "    ToolResultEvent,\n"
            "    ToolStartEvent,\n"
            "    UsageEvent,\n"
            ")\n"
            "\n"
            '__all__ = ["RunsEventsResource", "AsyncRunsEventsResource"]\n'
            "\n"
            "_SSEEventUnion = Annotated[\n"
            "    Union[\n"
            "        ApprovalRequiredEvent,\n"
            "        ContentDeltaEvent,\n"
            "        DoneEvent,\n"
            "        ErrorEvent,\n"
            "        OutputItemAddedEvent,\n"
            "        OutputItemDoneEvent,\n"
            "        ReasoningEvent,\n"
            "        ResponseCompletedEvent,\n"
            "        ResponseCreatedEvent,\n"
            "        ResponseFailedEvent,\n"
            "        RunCompletedEvent,\n"
            "        RunFailedEvent,\n"
            "        ToolProgressEvent,\n"
            "        ToolResultEvent,\n"
            "        ToolStartEvent,\n"
            "        UsageEvent,\n"
            "    ],\n"
            '    Field(discriminator="type"),\n'
            "]\n"
            "\n"
            "\n"
            "class RunsEventsResource(SyncAPIResource):\n"
            "    @cached_property\n"
            "    def with_raw_response(self) -> RunsEventsResourceWithRawResponse:\n"
            "        return RunsEventsResourceWithRawResponse(self)\n"
            "\n"
            "    @cached_property\n"
            "    def with_streaming_response(self) -> RunsEventsResourceWithStreamingResponse:\n"
            "        return RunsEventsResourceWithStreamingResponse(self)\n"
            "\n"
            "    def stream(\n"
            "        self,\n"
            "        *,\n"
            "        run_id: str,\n"
            "        extra_headers: Headers | None = None,\n"
            "        extra_query: Query | None = None,\n"
            "        extra_body: Body | None = None,\n"
            "        timeout: float | httpx.Timeout | None | NotGiven = not_given,\n"
            "    ) -> Stream[_SSEEventUnion]:\n"
            '        """Opens a Server-Sent Events stream for the specified run. Events include\n'
            "content deltas, tool executions, reasoning steps, approval requests,\n"
            'usage statistics, and completion/failure signals."""\n'
            "        return self._client._request(\n"
            '            "GET",\n'
            "            f\"/v1/runs/{quote(run_id, safe='')}/events\",\n"
            "            options=make_request_options(\n"
            "                extra_headers=extra_headers,\n"
            "                extra_query=extra_query,\n"
            "                extra_body=extra_body,\n"
            "                timeout=timeout,\n"
            "            ),\n"
            "            cast_to=_SSEEventUnion,\n"
            "            stream=True,\n"
            "            stream_cls=Stream,\n"
            "        )\n"
            "\n"
            "\n"
            "class AsyncRunsEventsResource(AsyncAPIResource):\n"
            "    @cached_property\n"
            "    def with_raw_response(self) -> AsyncRunsEventsResourceWithRawResponse:\n"
            "        return AsyncRunsEventsResourceWithRawResponse(self)\n"
            "\n"
            "    @cached_property\n"
            "    def with_streaming_response(self) -> AsyncRunsEventsResourceWithStreamingResponse:\n"
            "        return AsyncRunsEventsResourceWithStreamingResponse(self)\n"
            "\n"
            "    async def stream(\n"
            "        self,\n"
            "        *,\n"
            "        run_id: str,\n"
            "        extra_headers: Headers | None = None,\n"
            "        extra_query: Query | None = None,\n"
            "        extra_body: Body | None = None,\n"
            "        timeout: float | httpx.Timeout | None | NotGiven = not_given,\n"
            "    ) -> AsyncStream[_SSEEventUnion]:\n"
            '        """Opens a Server-Sent Events stream for the specified run. Events include\n'
            "content deltas, tool executions, reasoning steps, approval requests,\n"
            'usage statistics, and completion/failure signals."""\n'
            "        return await self._client._request(\n"
            '            "GET",\n'
            "            f\"/v1/runs/{quote(run_id, safe='')}/events\",\n"
            "            options=make_request_options(\n"
            "                extra_headers=extra_headers,\n"
            "                extra_query=extra_query,\n"
            "                extra_body=extra_body,\n"
            "                timeout=timeout,\n"
            "            ),\n"
            "            cast_to=_SSEEventUnion,\n"
            "            stream=True,\n"
            "            stream_cls=AsyncStream,\n"
            "        )\n"
            "\n"
            "\n"
            "class RunsEventsResourceWithRawResponse:\n"
            "    def __init__(self, runs_events: RunsEventsResource) -> None:\n"
            "        self.stream = to_raw_response_wrapper(runs_events.stream)\n"
            "\n"
            "\n"
            "class AsyncRunsEventsResourceWithRawResponse:\n"
            "    def __init__(self, runs_events: AsyncRunsEventsResource) -> None:\n"
            "        self.stream = async_to_raw_response_wrapper(runs_events.stream)\n"
            "\n"
            "\n"
            "class RunsEventsResourceWithStreamingResponse:\n"
            "    def __init__(self, runs_events: RunsEventsResource) -> None:\n"
            "        self.stream = to_streamed_response_wrapper(runs_events.stream)\n"
            "\n"
            "\n"
            "class AsyncRunsEventsResourceWithStreamingResponse:\n"
            "    def __init__(self, runs_events: AsyncRunsEventsResource) -> None:\n"
            "        self.stream = async_to_streamed_response_wrapper(runs_events.stream)\n"
        )
        print("  [patch] Fix 13: runs_events.py full rewrite (correct SSE streaming)")


def patch_runs_resources() -> None:
    for filename, paths_to_fix in (
        (
            "resources/runs.py",
            [
                ("from typing import List\n\nimport httpx", "from typing import List\nfrom urllib.parse import quote\n\nimport httpx"),
                ("f\"/v1/runs/{run_id}/stop\"", "f\"/v1/runs/{quote(run_id, safe='')}/stop\""),
            ],
        ),
        (
            "resources/runs_approval.py",
            [
                ("from functools import cached_property\n\nimport httpx", "from functools import cached_property\nfrom urllib.parse import quote\n\nimport httpx"),
                ("f\"/v1/runs/{run_id}/approval\"", "f\"/v1/runs/{quote(run_id, safe='')}/approval\""),
            ],
        ),
    ):
        path = SRC / filename
        print(f"Patching {path.relative_to(SDK_ROOT)} ...")
        text = path.read_text()
        for old, new in paths_to_fix:
            # replace ALL occurrences — both the sync and async methods share the
            # same unencoded path literal, so a single-shot replace would leave the
            # async variant unquoted.
            if old in text:
                text = text.replace(old, new)
                print(f"  [patch] Fix 8: URL-encode run_id in {filename} ({old[:40]!r})")
            else:
                print(f"  [skip]  Fix 8: {filename} ({old[:40]!r}) — already patched")
        path.write_text(text)


def main() -> None:
    print("=== post_generate.py: applying SDK patches ===")
    patch_shared_py()
    patch_base_client_py()
    patch_streaming_py()
    patch_params_files()
    patch_runs_create_response_py()
    patch_exceptions_py()
    patch_missing_bugfixes()
    patch_runs_resources()
    print("=== done ===")
    if _EXIT_CODE != 0:
        print("ERRORS encountered — one or more expected patterns not found.", file=sys.stderr)
        sys.exit(_EXIT_CODE)


if __name__ == "__main__":
    main()
