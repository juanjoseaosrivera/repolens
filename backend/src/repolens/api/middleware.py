"""Redis-backed rate limiting middleware.

Enforces per-IP request limits using a sliding-window counter in Redis.
"""

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from repolens.config import get_settings

log = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting backed by Redis."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip health/ready endpoints
        if request.url.path in ("/health", "/ready"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{client_ip}:{request.url.path}"

        try:
            from repolens.cache import get_cache

            cache = get_cache()
            allowed = await cache.check_rate_limit(
                key,
                limit=settings.rate_limit_per_minute,
                window=60,
            )

            if not allowed:
                log.warning("rate_limit.exceeded", ip=client_ip, path=request.url.path)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": "60"},
                )
        except Exception:
            # If Redis is down, allow the request through
            log.debug("rate_limit.redis_unavailable")

        return await call_next(request)
