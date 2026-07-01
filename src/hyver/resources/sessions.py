# Hand-maintained (not stainful-generated). The Hyver *loader* service owns
# session CRUD/history and runs at a different base URL than the runtime, so
# these methods target `client._loader_base_url` (set via `loader_base_url=` or
# `HYVER_LOADER_BASE_URL`) instead of the runtime base URL. Auth (the Cognito
# ID token) is identical to the runtime, so the same client credentials apply.
from __future__ import annotations

from functools import cached_property
from urllib.parse import quote

import httpx

from hyver._core._base_client import AsyncAPIClient, SyncAPIClient
from hyver._core._models import to_jsonable
from hyver._core._request_options import make_request_options
from hyver._core._resource import AsyncAPIResource, SyncAPIResource
from hyver._core._response import (
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
)
from hyver._core._sentinels import NotGiven, not_given
from hyver._core._types import Body, Headers, Query
from hyver.types import Session, SessionHistoryResponse, SessionListResponse

__all__ = ["SessionsResource", "AsyncSessionsResource"]


def _loader_base(client: SyncAPIClient | AsyncAPIClient) -> str:
    base: str | None = getattr(client, "_loader_base_url", None)
    if not base:
        raise ValueError(
            "Session endpoints require a loader base URL. Pass loader_base_url=... "
            "to the client or set the HYVER_LOADER_BASE_URL environment variable."
        )
    return base


class SessionsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SessionsResourceWithRawResponse:
        return SessionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SessionsResourceWithStreamingResponse:
        return SessionsResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        title: str | NotGiven = not_given,
        model_config: dict[str, object] | NotGiven = not_given,
        session_attributes: dict[str, object] | NotGiven = not_given,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Session:
        """Create a new session. Returns the session (use ``.session_id`` as the
        ``session_id`` for ``client.runs.create``)."""
        body = {"title": title, "modelConfig": model_config, "sessionAttributes": session_attributes}
        body = {k: v for k, v in body.items() if not isinstance(v, NotGiven)}
        return self._post(
            f"{_loader_base(self._client)}/sessions",
            body=to_jsonable(body),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Session,
        )

    def list(
        self,
        *,
        status: str | NotGiven = not_given,
        limit: int | NotGiven = not_given,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SessionListResponse:
        """List the authenticated user's sessions (newest first)."""
        params: dict[str, object] = {}
        if not isinstance(status, NotGiven):
            params["status"] = status
        if not isinstance(limit, NotGiven):
            params["limit"] = limit
        return self._get(
            f"{_loader_base(self._client)}/sessions",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                params=params,
            ),
            cast_to=SessionListResponse,
        )

    def retrieve(
        self,
        *,
        session_id: str,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Session:
        """Fetch a single session by id."""
        return self._get(
            f"{_loader_base(self._client)}/sessions/{quote(session_id, safe='')}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Session,
        )

    def delete(
        self,
        *,
        session_id: str,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """End (delete) a session. Returns ``None`` (HTTP 204)."""
        return self._delete(
            f"{_loader_base(self._client)}/sessions/{quote(session_id, safe='')}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=type(None),
        )

    def history(
        self,
        *,
        session_id: str,
        limit: int | NotGiven = not_given,
        offset: int | NotGiven = not_given,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SessionHistoryResponse:
        """Fetch paginated message history for a session."""
        params: dict[str, object] = {}
        if not isinstance(limit, NotGiven):
            params["limit"] = limit
        if not isinstance(offset, NotGiven):
            params["offset"] = offset
        return self._get(
            f"{_loader_base(self._client)}/sessions/{quote(session_id, safe='')}/history",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                params=params,
            ),
            cast_to=SessionHistoryResponse,
        )


class AsyncSessionsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSessionsResourceWithRawResponse:
        return AsyncSessionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSessionsResourceWithStreamingResponse:
        return AsyncSessionsResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        title: str | NotGiven = not_given,
        model_config: dict[str, object] | NotGiven = not_given,
        session_attributes: dict[str, object] | NotGiven = not_given,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Session:
        """Create a new session. Returns the session (use ``.session_id`` as the
        ``session_id`` for ``client.runs.create``)."""
        body = {"title": title, "modelConfig": model_config, "sessionAttributes": session_attributes}
        body = {k: v for k, v in body.items() if not isinstance(v, NotGiven)}
        return await self._post(
            f"{_loader_base(self._client)}/sessions",
            body=to_jsonable(body),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Session,
        )

    async def list(
        self,
        *,
        status: str | NotGiven = not_given,
        limit: int | NotGiven = not_given,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SessionListResponse:
        """List the authenticated user's sessions (newest first)."""
        params: dict[str, object] = {}
        if not isinstance(status, NotGiven):
            params["status"] = status
        if not isinstance(limit, NotGiven):
            params["limit"] = limit
        return await self._get(
            f"{_loader_base(self._client)}/sessions",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                params=params,
            ),
            cast_to=SessionListResponse,
        )

    async def retrieve(
        self,
        *,
        session_id: str,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Session:
        """Fetch a single session by id."""
        return await self._get(
            f"{_loader_base(self._client)}/sessions/{quote(session_id, safe='')}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Session,
        )

    async def delete(
        self,
        *,
        session_id: str,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """End (delete) a session. Returns ``None`` (HTTP 204)."""
        return await self._delete(
            f"{_loader_base(self._client)}/sessions/{quote(session_id, safe='')}",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=type(None),
        )

    async def history(
        self,
        *,
        session_id: str,
        limit: int | NotGiven = not_given,
        offset: int | NotGiven = not_given,
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SessionHistoryResponse:
        """Fetch paginated message history for a session."""
        params: dict[str, object] = {}
        if not isinstance(limit, NotGiven):
            params["limit"] = limit
        if not isinstance(offset, NotGiven):
            params["offset"] = offset
        return await self._get(
            f"{_loader_base(self._client)}/sessions/{quote(session_id, safe='')}/history",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                params=params,
            ),
            cast_to=SessionHistoryResponse,
        )


class SessionsResourceWithRawResponse:
    def __init__(self, sessions: SessionsResource) -> None:
        self.create = to_raw_response_wrapper(sessions.create)
        self.list = to_raw_response_wrapper(sessions.list)
        self.retrieve = to_raw_response_wrapper(sessions.retrieve)
        self.delete = to_raw_response_wrapper(sessions.delete)
        self.history = to_raw_response_wrapper(sessions.history)


class AsyncSessionsResourceWithRawResponse:
    def __init__(self, sessions: AsyncSessionsResource) -> None:
        self.create = async_to_raw_response_wrapper(sessions.create)
        self.list = async_to_raw_response_wrapper(sessions.list)
        self.retrieve = async_to_raw_response_wrapper(sessions.retrieve)
        self.delete = async_to_raw_response_wrapper(sessions.delete)
        self.history = async_to_raw_response_wrapper(sessions.history)


class SessionsResourceWithStreamingResponse:
    def __init__(self, sessions: SessionsResource) -> None:
        self.create = to_streamed_response_wrapper(sessions.create)
        self.list = to_streamed_response_wrapper(sessions.list)
        self.retrieve = to_streamed_response_wrapper(sessions.retrieve)
        self.delete = to_streamed_response_wrapper(sessions.delete)
        self.history = to_streamed_response_wrapper(sessions.history)


class AsyncSessionsResourceWithStreamingResponse:
    def __init__(self, sessions: AsyncSessionsResource) -> None:
        self.create = async_to_streamed_response_wrapper(sessions.create)
        self.list = async_to_streamed_response_wrapper(sessions.list)
        self.retrieve = async_to_streamed_response_wrapper(sessions.retrieve)
        self.delete = async_to_streamed_response_wrapper(sessions.delete)
        self.history = async_to_streamed_response_wrapper(sessions.history)
