"""Domain exception hierarchy for RepoLens."""

from repolens.errors.exceptions import (
    AgentError,
    IngestionError,
    RepoLensError,
    RetrievalError,
)

__all__ = [
    "AgentError",
    "IngestionError",
    "RepoLensError",
    "RetrievalError",
]
