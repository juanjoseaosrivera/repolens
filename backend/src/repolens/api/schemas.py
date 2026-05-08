"""Pydantic request / response schemas for the RepoLens API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class RepoCreate(BaseModel):
    """Request body for creating (and ingesting) a repository."""

    url: str = Field(..., min_length=1, max_length=2048, description="Git clone URL")
    name: str | None = Field(
        None,
        max_length=255,
        description="Display name. Derived from URL if omitted.",
    )


class RepoOut(BaseModel):
    """Public representation of a repository."""

    id: uuid.UUID
    name: str
    url: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for the chat / Q&A endpoint."""

    repository_id: uuid.UUID
    question: str = Field(..., min_length=1, max_length=10_000)


class ChunkContext(BaseModel):
    """A retrieved chunk shown alongside the answer."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float
