"""Auto-pagination — symbol-compatible with openai-python (§5a).

RESEARCH §4 #1: `for item in client.things.list(): ...` transparently walks
EVERY page. The page object carries the client + request context so iterating
it fetches subsequent pages on demand (sync `__iter__`, async `__aiter__`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, replace
from typing import (
    Any,
    Generic,
    TypeVar,
)

from pydantic import PrivateAttr

from ._models import BaseModel

_T = TypeVar("_T")

__all__ = [
    "PageInfo",
    "SyncPage",
    "AsyncPage",
    "SyncCursorPage",
    "AsyncCursorPage",
    "SyncBiDirectionalPage",
    "AsyncBiDirectionalPage",
]


@dataclass
class PageInfo:
    """How to fetch the next page: query-param delta or an absolute url."""

    params: dict | None = None
    url: str | None = None


class BasePage(BaseModel, Generic[_T]):
    # injected by the client after parsing (not wire fields)
    _client: Any = PrivateAttr(default=None)
    _path: str = PrivateAttr(default="")
    _page_cls: Any = PrivateAttr(default=None)
    _options: Any = PrivateAttr(default=None)
    # Per-call pagination config from the generator
    # (e.g. `{"cursor_param": "after", "cursor_response_field": "last_id"}`).
    # `None` → runtime defaults — see `_CursorPage.next_page_info`.
    _pagination_cfg: dict | None = PrivateAttr(default=None)

    def _init_pagination(
        self, client, path, page_cls, options, pagination_cfg=None
    ) -> BasePage:
        self._client = client
        self._path = path
        self._page_cls = page_cls
        self._options = options
        self._pagination_cfg = pagination_cfg
        return self

    def _get_page_items(self) -> list[_T]:  # pragma: no cover - overridden
        raise NotImplementedError

    def next_page_info(self) -> PageInfo | None:  # pragma: no cover
        return None

    def has_next_page(self) -> bool:
        return self.next_page_info() is not None


def _walk_sync(page: BasePage) -> Iterator[Any]:
    while True:
        yield from page._get_page_items()
        info = page.next_page_info()
        if info is None or page._client is None:
            return
        page = page._client._paginate_next(
            page._path, page._page_cls, page._options, info,
            pagination_cfg=page._pagination_cfg,
        )


async def _walk_async(page: BasePage) -> AsyncIterator[Any]:
    while True:
        for item in page._get_page_items():
            yield item
        info = page.next_page_info()
        if info is None or page._client is None:
            return
        page = await page._client._paginate_next(
            page._path, page._page_cls, page._options, info,
            pagination_cfg=page._pagination_cfg,
        )


class SyncPage(BasePage[_T], Generic[_T]):
    """`{"data": [...], "object": "list"}` — single page (no next)."""

    data: list[_T]
    object: str | None = None

    def _get_page_items(self) -> list[_T]:
        return self.data or []

    def next_page_info(self) -> PageInfo | None:
        return None

    def __iter__(self) -> Iterator[_T]:  # type: ignore[override]
        # deliberately iterates ITEMS (auto-paginating), not pydantic fields
        return _walk_sync(self)


class AsyncPage(BasePage[_T], Generic[_T]):
    data: list[_T]
    object: str | None = None

    def _get_page_items(self) -> list[_T]:
        return self.data or []

    def next_page_info(self) -> PageInfo | None:
        return None

    def __aiter__(self) -> AsyncIterator[_T]:
        return _walk_async(self)


class _CursorPage(BasePage[_T], Generic[_T]):
    data: list[_T]
    has_more: bool | None = None
    next_cursor: str | None = None

    def _get_page_items(self) -> list[_T]:
        return self.data or []

    def next_page_info(self) -> PageInfo | None:
        if self.has_more is False or not self.data:
            return None
        cfg = self._pagination_cfg or {}
        # Wire param name: `after` matches openai/anthropic SyncCursorPage —
        # use that as the safe default rather than the literal "cursor",
        # which silently fails against any API expecting `after`.
        param = cfg.get("cursor_param") or "after"
        field = cfg.get("cursor_response_field")
        cursor: str | None = None
        if field is not None:
            cursor = getattr(self, field, None)  # extra="allow" → attrs available
        if cursor is None:
            cursor = self.next_cursor
        if cursor is None:
            cursor = getattr(self.data[-1], "id", None)
        if cursor is None:
            return None
        return PageInfo(params={param: cursor})


class SyncCursorPage(_CursorPage[_T], Generic[_T]):
    def __iter__(self) -> Iterator[_T]:  # type: ignore[override]
        # deliberately iterates ITEMS (auto-paginating), not pydantic fields
        return _walk_sync(self)


class AsyncCursorPage(_CursorPage[_T], Generic[_T]):
    def __aiter__(self) -> AsyncIterator[_T]:
        return _walk_async(self)


class _BiDirectionalPage(BasePage[_T], Generic[_T]):
    """Anthropic-shape pagination: pick `before_id`/`after_id` based on
    which the *initial* request set. Forward direction is the default
    (returns `after_id=<last_id>`); reverse if the user originally
    passed `before_id`, the page emits `before_id=<first_id>` on the
    next-page request.

    Field/param names are configurable via `_pagination_cfg` for specs
    that share the algorithm but use different names; defaults match
    anthropic-sdk-python's `SyncPage`.
    """

    data: list[_T]
    has_more: bool | None = None
    first_id: str | None = None
    last_id: str | None = None

    def _get_page_items(self) -> list[_T]:
        return self.data or []

    def next_page_info(self) -> PageInfo | None:
        if self.has_more is False or not self.data:
            return None
        cfg = self._pagination_cfg or {}
        before_param = cfg.get("before_param") or "before_id"
        after_param = cfg.get("after_param") or "after_id"
        first_field = cfg.get("first_field") or "first_id"
        last_field = cfg.get("last_field") or "last_id"
        # Initial-request direction. `_options.params` is the dict of
        # query params that originally went out — if it carried the
        # `before_param`, the user is walking backwards.
        params = (
            getattr(self._options, "params", None) if self._options else None
        ) or {}
        if params.get(before_param):
            first_id = getattr(self, first_field, None)
            if not first_id:
                return None
            return PageInfo(params={before_param: first_id})
        last_id = getattr(self, last_field, None)
        if not last_id:
            return None
        return PageInfo(params={after_param: last_id})


class SyncBiDirectionalPage(_BiDirectionalPage[_T], Generic[_T]):
    def __iter__(self) -> Iterator[_T]:  # type: ignore[override]
        return _walk_sync(self)


class AsyncBiDirectionalPage(_BiDirectionalPage[_T], Generic[_T]):
    def __aiter__(self) -> AsyncIterator[_T]:
        return _walk_async(self)


def merge_options(options, info: PageInfo):
    """Return request options for the next page (cursor merged into params)."""
    params = {**(getattr(options, "params", None) or {}), **(info.params or {})}
    return replace(options, params=params)
