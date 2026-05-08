"""Git clone / fetch utility.

Uses subprocess to call git directly — no extra dependencies needed.
"""

import asyncio
import hashlib
import shutil
from pathlib import Path

import structlog

from repolens.config import get_settings
from repolens.errors import IngestionError

log = structlog.get_logger(__name__)


async def clone_repo(url: str, *, force: bool = False) -> tuple[Path, str]:
    """Clone a git repository and return (local_path, commit_hash).

    If the directory already exists and *force* is False, performs a ``git pull``
    instead.  The commit hash is the HEAD SHA after clone/pull.

    Raises:
        IngestionError: if the git command fails.
    """
    settings = get_settings()
    base = Path(settings.clone_base_dir)
    base.mkdir(parents=True, exist_ok=True)

    repo_name = _url_to_dirname(url)
    dest = base / repo_name

    if dest.exists() and force:
        shutil.rmtree(dest)

    if dest.exists():
        log.info("ingestion.pull", url=url, dest=str(dest))
        await _run_git("pull", cwd=dest)
    else:
        log.info("ingestion.clone", url=url, dest=str(dest))
        await _run_git("clone", "--depth=1", url, str(dest))

    commit_hash = await _get_head_sha(dest)
    log.info("ingestion.clone_done", url=url, commit=commit_hash)
    return dest, commit_hash


def _url_to_dirname(url: str) -> str:
    """Derive a safe directory name from a git URL."""
    safe = url.rstrip("/").rsplit("/", maxsplit=1)[-1].removesuffix(".git")
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
    return f"{safe}-{url_hash}"


async def _run_git(*args: str, cwd: Path | None = None) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode().strip() or stdout.decode().strip()
        raise IngestionError(f"git {args[0]} failed: {msg}")
    return stdout.decode().strip()


async def _get_head_sha(repo_path: Path) -> str:
    return await _run_git("rev-parse", "HEAD", cwd=repo_path)
