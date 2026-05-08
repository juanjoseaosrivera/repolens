"""SQLAlchemy ORM base, shared column mixins, and domain models.

Phase 1 tables: repositories, files, chunks (with pgvector embeddings).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all RepoLens ORM models."""


class TimestampMixin:
    """Mixin providing created_at / updated_at columns on every table."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Mixin providing a UUID v4 primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A code repository that has been registered for analysis."""

    __tablename__ = "repositories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    clone_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    files: Mapped[list["File"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Repository {self.name!r} status={self.status!r}>"


class File(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single file within a repository."""

    __tablename__ = "files"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="files")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_files_repository_id", "repository_id"),
        Index("ix_files_content_hash", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<File {self.path!r}>"


class Chunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A code chunk extracted from a file, with its embedding vector."""

    __tablename__ = "chunks"

    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    start_line: Mapped[int] = mapped_column(nullable=False)
    end_line: Mapped[int] = mapped_column(nullable=False)
    token_count: Mapped[int | None] = mapped_column(nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )

    file: Mapped["File"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_file_id", "file_id"),
        Index("ix_chunks_content_hash", "content_hash"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Chunk file_id={self.file_id!r} lines={self.start_line}-{self.end_line}>"
