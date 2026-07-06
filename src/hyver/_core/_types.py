"""Shared type aliases — symbol-compatible with openai-python (DESIGN §5a)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import IO, Any, Union

from ._sentinels import Omit, Omittable

# A header value may be explicitly removed with `omit`.
Headers = Mapping[str, str | Omit]
Query = Mapping[str, object]
Body = object

# A multipart file field — symbol-compatible with openai-python: raw bytes,
# a binary file object, or a (filename, content[, content_type]) tuple.
FileTypes = Union[
    IO[bytes],
    bytes,
    tuple[str | None, IO[bytes] | bytes],
    tuple[str | None, IO[bytes] | bytes, str | None],
]

__all__ = ["Headers", "Query", "Body", "FileTypes", "Omittable", "Any"]
