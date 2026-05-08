"""Ingestion pipeline — orchestrates clone → walk → chunk → embed → store.

Phase 2: uses AST chunker with naive fallback, sensitive-content filter,
and enriches chunks with symbols_defined / imports metadata.
"""

import hashlib
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from repolens.config import get_settings
from repolens.errors import IngestionError
from repolens.ingestion.ast_chunker import ast_chunk_file
from repolens.ingestion.clone import clone_repo
from repolens.ingestion.filter import redact_secrets, should_skip_file
from repolens.ingestion.walker import walk_repo
from repolens.llm import EmbeddingClient
from repolens.storage.models import Chunk, File, Repository

log = structlog.get_logger(__name__)


async def run_ingestion(
    repository_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Full ingestion pipeline for a single repository.

    1. Set status to ``ingesting``.
    2. Clone / pull the repo.
    3. Walk files, chunk (AST or naive), embed (batched), and store.
    4. Set status to ``ready`` (or ``failed`` on error).
    """
    async with session_factory() as session:
        repo = await session.get(Repository, repository_id)
        if repo is None:
            log.error("pipeline.repo_not_found", repository_id=str(repository_id))
            return

        repo.status = "ingesting"
        await session.commit()

    try:
        await _ingest(repository_id, session_factory)
    except Exception as exc:
        log.error(
            "pipeline.failed",
            repository_id=str(repository_id),
            error=str(exc),
        )
        async with session_factory() as session:
            repo = await session.get(Repository, repository_id)
            if repo:
                repo.status = "failed"
                await session.commit()
        raise IngestionError(f"Ingestion failed: {exc}") from exc


async def _ingest(
    repository_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    embedder = EmbeddingClient()

    async with session_factory() as session:
        repo = await session.get(Repository, repository_id)
        assert repo is not None

        # Clone / pull
        clone_path, commit_hash = await clone_repo(repo.url)

        # Skip if content hash unchanged (idempotent re-ingestion)
        if repo.content_hash == commit_hash:
            log.info("pipeline.no_changes", repository_id=str(repository_id))
            repo.status = "ready"
            await session.commit()
            return

        # Clear old data for re-ingestion
        existing_files = (
            (await session.execute(select(File).where(File.repository_id == repository_id)))
            .scalars()
            .all()
        )
        for f in existing_files:
            await session.delete(f)
        await session.flush()

        repo.clone_path = str(clone_path)
        repo.content_hash = commit_hash

        # Walk → filter → chunk (AST with naive fallback)
        all_chunks: list[tuple[File, list[tuple[str, int, int, list[str], list[str]]]]] = []
        file_count = 0
        chunk_count = 0
        skipped_sensitive = 0

        for rel_path, content, language in walk_repo(clone_path):
            # Sensitive-content filter
            if should_skip_file(rel_path):
                skipped_sensitive += 1
                continue

            content_hash = hashlib.sha256(content.encode()).hexdigest()

            file_obj = File(
                id=uuid.uuid4(),
                repository_id=repository_id,
                path=rel_path,
                content_hash=content_hash,
                language=language,
            )
            session.add(file_obj)
            file_count += 1

            # Redact secrets from content before chunking
            safe_content = redact_secrets(content)

            # AST chunker (falls back to naive for unsupported languages)
            ast_chunks = ast_chunk_file(safe_content, language)
            chunk_data: list[tuple[str, int, int, list[str], list[str]]] = []
            for ac in ast_chunks:
                chunk_data.append(
                    (
                        ac.content,
                        ac.start_line,
                        ac.end_line,
                        ac.symbols_defined,
                        ac.imports,
                    )
                )
                chunk_count += 1

            if chunk_data:
                all_chunks.append((file_obj, chunk_data))

        log.info(
            "pipeline.chunked",
            repository_id=str(repository_id),
            files=file_count,
            chunks=chunk_count,
            skipped_sensitive=skipped_sensitive,
        )

        # Embed in batches and store chunks
        batch_size = settings.embedding_batch_size
        flat_texts: list[str] = []
        flat_meta: list[tuple[File, int, int, str, list[str], list[str]]] = []

        for file_obj, chunk_data in all_chunks:
            for text, start, end, symbols, imports in chunk_data:
                flat_texts.append(text)
                flat_meta.append((file_obj, start, end, text, symbols, imports))

        for i in range(0, len(flat_texts), batch_size):
            batch_texts = flat_texts[i : i + batch_size]
            batch_meta = flat_meta[i : i + batch_size]

            vectors = await embedder.embed(batch_texts)

            for (file_obj, start, end, text, symbols, imports), vector in zip(
                batch_meta, vectors, strict=True
            ):
                chunk_hash = hashlib.sha256(text.encode()).hexdigest()
                chunk_obj = Chunk(
                    id=uuid.uuid4(),
                    file_id=file_obj.id,
                    content=text,
                    content_hash=chunk_hash,
                    start_line=start,
                    end_line=end,
                    embedding=vector,
                    symbols_defined=symbols if symbols else None,
                    imports=imports if imports else None,
                )
                session.add(chunk_obj)

            log.info(
                "pipeline.embedded_batch",
                repository_id=str(repository_id),
                batch=i // batch_size + 1,
                size=len(batch_texts),
            )

        repo.status = "ready"
        await session.commit()

        # Phase 3: build dependency graph in Neo4j (best-effort)
        try:
            from repolens.ingestion.graph_pass import build_graph_from_repo

            await build_graph_from_repo(str(repository_id), clone_path)
        except Exception:
            log.warning("pipeline.graph_build_skipped", repository_id=str(repository_id))

        log.info(
            "pipeline.complete",
            repository_id=str(repository_id),
            files=file_count,
            chunks=chunk_count,
        )
