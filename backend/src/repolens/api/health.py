"""Health and readiness endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    """Readiness probe — the app can serve traffic.

    TODO(phase-1): Check database connectivity here.
    """
    return {"status": "ready"}
