"""Repository management endpoints — create, list, get status."""

import uuid

import structlog
from arq.connections import ArqRedis, create_pool
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repolens.api.deps import get_session
from repolens.api.schemas import RepoCreate, RepoOut
from repolens.storage.models import Repository
from repolens.worker import WorkerSettings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/repos", tags=["repositories"])


async def _get_arq_pool() -> ArqRedis:
    return await create_pool(WorkerSettings.redis_settings)


@router.post("", response_model=RepoOut, status_code=201)
async def create_repo(
    body: RepoCreate,
    session: AsyncSession = Depends(get_session),
) -> Repository:
    """Register a repository and enqueue ingestion."""
    # Derive name from URL if not provided
    name = body.name or body.url.rstrip("/").rsplit("/", maxsplit=1)[-1].removesuffix(".git")

    # Check for duplicate URL
    existing = (
        await session.execute(select(Repository).where(Repository.url == body.url))
    ).scalar_one_or_none()

    if existing is not None:
        # Re-trigger ingestion if previously failed
        if existing.status == "failed":
            existing.status = "pending"
            await session.commit()
            await _enqueue_ingestion(existing.id)
            await session.refresh(existing)
            return existing
        raise HTTPException(status_code=409, detail="Repository already registered")

    repo = Repository(id=uuid.uuid4(), name=name, url=body.url)
    session.add(repo)
    await session.commit()
    await session.refresh(repo)

    await _enqueue_ingestion(repo.id)

    log.info("repos.created", id=str(repo.id), url=body.url)
    return repo


@router.get("", response_model=list[RepoOut])
async def list_repos(
    session: AsyncSession = Depends(get_session),
) -> list[Repository]:
    """List all registered repositories."""
    result = await session.execute(select(Repository).order_by(Repository.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repo(
    repo_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Repository:
    """Get a single repository by ID."""
    repo = await session.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
async def delete_repo(
    repo_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a repository and all associated files/chunks (cascaded)."""
    repo = await session.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    await session.delete(repo)
    await session.commit()
    log.info("repos.deleted", id=str(repo_id))


async def _enqueue_ingestion(repo_id: uuid.UUID) -> None:
    """Enqueue an ingestion job via arq."""
    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("ingest_repo", str(repo_id))
        log.info("repos.ingestion_enqueued", repo_id=str(repo_id))
    except Exception:
        log.warning(
            "repos.arq_unavailable",
            repo_id=str(repo_id),
            detail="arq worker not reachable — ingestion will not run until worker starts",
        )
