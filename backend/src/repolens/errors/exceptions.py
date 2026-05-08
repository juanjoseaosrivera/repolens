"""Domain exception hierarchy.

Catch only what you can handle. Re-raise with context using ``raise ... from err``.
"""


class RepoLensError(Exception):
    """Base exception for all RepoLens domain errors."""

    def __init__(self, message: str = "", *, detail: str | None = None) -> None:
        self.detail = detail or message
        super().__init__(message)


class IngestionError(RepoLensError):
    """Raised when the ingestion pipeline fails (clone, parse, chunk, embed, index)."""


class RetrievalError(RepoLensError):
    """Raised when the retrieval layer cannot produce results."""


class AgentError(RepoLensError):
    """Raised when the LangGraph agent encounters an unrecoverable condition."""


class ConfigurationError(RepoLensError):
    """Raised when required configuration is missing or invalid."""


class StorageError(RepoLensError):
    """Raised when a database operation fails."""
