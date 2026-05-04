"""End-to-end ingestion: walk → chunk → embed → upsert."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from repolens.db.engine import get_session
from repolens.db.models import Chunk, Repo
from repolens.embeddings import Embedder
from repolens.ingest.chunker_naive import TextChunk, chunk_text
from repolens.ingest.walker import WalkedFile, walk

DEFAULT_EMBED_BATCH = 64


@dataclass(frozen=True, slots=True)
class IngestStats:
    repo_id: int
    files_seen: int
    chunks_written: int


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_records(
    walked: WalkedFile,
    chunks: Iterable[TextChunk],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for idx, c in enumerate(chunks):
        records.append(
            {
                "file_path": walked.relative_path,
                "language": walked.language,
                "chunk_index": idx,
                "start_char": c.start_char,
                "end_char": c.end_char,
                "content": c.text,
                "content_hash": _hash(c.text),
            }
        )
    return records


def _get_or_create_repo(session: Session, name: str, root_path: str) -> Repo:
    repo = session.execute(select(Repo).where(Repo.name == name)).scalar_one_or_none()
    if repo is None:
        repo = Repo(name=name, root_path=root_path)
        session.add(repo)
        session.flush()
    else:
        repo.root_path = root_path
    return repo


def ingest_repo(
    repo_path: str | Path,
    *,
    name: str | None = None,
    embedder: Embedder | None = None,
    batch_size: int = DEFAULT_EMBED_BATCH,
) -> IngestStats:
    """Ingest a local repo into Postgres. Idempotent on repo name."""
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")
    repo_name = name or root.name
    embedder = embedder or Embedder()

    pending: list[dict[str, object]] = []
    files_seen = 0

    with get_session() as session:
        repo = _get_or_create_repo(session, name=repo_name, root_path=str(root))
        # Naive re-ingestion: drop existing chunks and rewrite. Phase 4 will
        # do incremental ingestion via content_hash.
        session.execute(delete(Chunk).where(Chunk.repo_id == repo.id))
        repo_id = repo.id

        for walked in walk(root):
            files_seen += 1
            chunks = chunk_text(walked.content)
            if not chunks:
                continue
            pending.extend(_chunk_records(walked, chunks))

        chunks_written = _embed_and_upsert(
            session, repo_id=repo_id, records=pending, embedder=embedder, batch_size=batch_size
        )

    return IngestStats(repo_id=repo_id, files_seen=files_seen, chunks_written=chunks_written)


def _embed_and_upsert(
    session: Session,
    *,
    repo_id: int,
    records: list[dict[str, object]],
    embedder: Embedder,
    batch_size: int,
) -> int:
    total = 0
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        texts = [r["content"] for r in batch]
        vectors = embedder.embed([t if isinstance(t, str) else "" for t in texts])
        rows = [
            {**rec, "repo_id": repo_id, "embedding": vec}
            for rec, vec in zip(batch, vectors, strict=True)
        ]
        stmt = pg_insert(Chunk).values(rows)
        update_cols = {
            "language": stmt.excluded.language,
            "start_char": stmt.excluded.start_char,
            "end_char": stmt.excluded.end_char,
            "content": stmt.excluded.content,
            "content_hash": stmt.excluded.content_hash,
            "embedding": stmt.excluded.embedding,
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_chunks_repo_file_index",
            set_=update_cols,
        )
        session.execute(stmt)
        total += len(rows)
    return total
