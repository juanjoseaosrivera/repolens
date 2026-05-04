"""Vector search over the chunks table using pgvector cosine distance."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from repolens.db.engine import get_session
from repolens.db.models import Chunk, Repo
from repolens.embeddings import Embedder


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    repo_name: str
    file_path: str
    language: str | None
    chunk_index: int
    start_char: int
    end_char: int
    content: str
    distance: float

    @property
    def score(self) -> float:
        """Cosine similarity in [-1, 1] derived from cosine distance in [0, 2]."""
        return 1.0 - self.distance


def search(
    query: str,
    *,
    top_k: int = 5,
    repo_name: str | None = None,
    embedder: Embedder | None = None,
) -> list[RetrievedChunk]:
    if not query.strip():
        return []

    embedder = embedder or Embedder()
    [query_vec] = embedder.embed([query])

    distance = Chunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(
            Repo.name.label("repo_name"),
            Chunk.file_path,
            Chunk.language,
            Chunk.chunk_index,
            Chunk.start_char,
            Chunk.end_char,
            Chunk.content,
            distance.label("distance"),
        )
        .join(Repo, Repo.id == Chunk.repo_id)
        .order_by(distance)
        .limit(top_k)
    )
    if repo_name is not None:
        stmt = stmt.where(Repo.name == repo_name)

    with get_session() as session:
        rows = session.execute(stmt).all()

    return [
        RetrievedChunk(
            repo_name=row.repo_name,
            file_path=row.file_path,
            language=row.language,
            chunk_index=row.chunk_index,
            start_char=row.start_char,
            end_char=row.end_char,
            content=row.content,
            distance=float(row.distance),
        )
        for row in rows
    ]
