# Hand-maintained (not stainful-generated): the Hyver *loader* service owns
# session CRUD/history and lives at a different base URL than the runtime, so it
# is not part of the runtime openapi.yaml. Keep this in sync with the loader API.
from __future__ import annotations

from pydantic import Field

from .._core._models import BaseModel

__all__ = [
    "Session",
    "SessionHistoryPagination",
    "SessionHistoryResponse",
    "SessionListResponse",
]


class Session(BaseModel):
    """A Hyver session. Unknown/forward-compatible fields (e.g. ``modelConfig``,
    ``sessionAttributes``, ``memory``) are preserved via ``extra="allow"``."""

    session_id: str | None = Field(default=None, alias="sessionId")
    user_id: str | None = Field(default=None, alias="userId")
    tenant_id: str | None = Field(default=None, alias="tenantId")
    status: str | None = None
    title: str | None = None
    message_count: int | None = Field(default=None, alias="messageCount")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    last_message_at: str | None = Field(default=None, alias="lastMessageAt")
    agent_id: str | None = Field(default=None, alias="agentId")
    latest_job_id: str | None = Field(default=None, alias="latestJobId")
    latest_job_status: str | None = Field(default=None, alias="latestJobStatus")


class SessionListResponse(BaseModel):
    """Response of ``GET /sessions`` — the user's sessions, newest first."""

    sessions: list[Session] = Field(default_factory=list)


class SessionHistoryPagination(BaseModel):
    offset: int | None = None
    limit: int | None = None
    total: int | None = None
    has_more: bool | None = Field(default=None, alias="hasMore")


class SessionHistoryResponse(BaseModel):
    """Response of ``GET /sessions/{id}/history`` — paginated message history."""

    session_id: str | None = Field(default=None, alias="sessionId")
    messages: list[dict[str, object]] = Field(default_factory=list)
    pagination: SessionHistoryPagination | None = None
