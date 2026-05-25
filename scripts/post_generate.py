"""Post-generation patch script for stainful-generated Hermes SDK.

Run after `make generate` to apply fixes that stainful cannot express.
All patches are idempotent: safe to re-run after any regeneration.
"""

from __future__ import annotations

import sys
from pathlib import Path

SDK_ROOT = Path(__file__).parent.parent
SRC = SDK_ROOT / "src" / "hermes"

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
        "                    data=sse.json(), cast_to=self._cast_to, response=self._response\n"
        "                )\n"
        "            sse = self._decoder.flush()\n"
        "            if sse is not None and sse.data.strip() not in (\"\", \"[DONE]\"):\n"
        "                yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                    data=sse.json(), cast_to=self._cast_to, response=self._response\n"
        "                )\n"
        "        finally:\n"
        "            self._response.close()\n",
        "Fix 3b: Stream.__iter__ try/finally auto-close + flush",
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
        "                    data=sse.json(), cast_to=self._cast_to, response=self._response\n"
        "                )\n"
        "            sse = self._decoder.flush()\n"
        "            if sse is not None and sse.data.strip() not in (\"\", \"[DONE]\"):\n"
        "                yield self._client._process_response_data(  # type: ignore[attr-defined]\n"
        "                    data=sse.json(), cast_to=self._cast_to, response=self._response\n"
        "                )\n"
        "        finally:\n"
        "            await self._response.aclose()\n",
        "Fix 3d: AsyncStream.__aiter__ try/finally auto-close + flush",
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
    chat_path = SRC / "types" / "chat_completions_create_params.py"
    print(f"Patching {chat_path.relative_to(SDK_ROOT)} ...")
    _patch(
        chat_path,
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, TypedDict, Union,\n"
        ")",
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, Required, TypedDict, Union,\n"
        ")",
        "Fix 4a: add Required import",
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
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, TypedDict, Union,\n"
        ")",
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, Required, TypedDict, Union,\n"
        ")",
        "Fix 4c: add Required import",
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
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, TypedDict, Union,\n"
        ")",
        "from typing import (  # noqa: F401\n"
        "    Annotated, Any, Dict, List, Literal, Optional, Required, TypedDict, Union,\n"
        ")",
        "Fix 4e: add Required import",
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
            "resources/runs_events.py",
            [
                ("from typing import Annotated, Union\n\nimport httpx", "from typing import Annotated, Union\nfrom urllib.parse import quote\n\nimport httpx"),
                ("f\"/v1/runs/{run_id}/events\"", "f\"/v1/runs/{quote(run_id, safe='')}/events\""),
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
        for old, new in paths_to_fix:
            label = f"Fix 8: URL-encode run_id in {filename} ({old[:40]!r})"
            _patch(path, old, new, label)


def main() -> None:
    print("=== post_generate.py: applying SDK patches ===")
    patch_shared_py()
    patch_base_client_py()
    patch_streaming_py()
    patch_params_files()
    patch_runs_create_response_py()
    patch_exceptions_py()
    patch_runs_resources()
    print("=== done ===")
    if _EXIT_CODE != 0:
        print("ERRORS encountered — one or more expected patterns not found.", file=sys.stderr)
        sys.exit(_EXIT_CODE)


if __name__ == "__main__":
    main()
