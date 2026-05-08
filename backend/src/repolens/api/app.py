"""FastAPI application factory."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from repolens.api.agent_chat import router as agent_router
from repolens.api.chat import router as chat_router
from repolens.api.health import router as health_router
from repolens.api.middleware import RateLimitMiddleware
from repolens.api.repos import router as repos_router
from repolens.config import get_settings
from repolens.observability.logging import setup_logging
from repolens.observability.tracing import instrument_fastapi, setup_tracing


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Inject a trace ID into every response for frontend error correlation."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: set up and tear down shared resources."""
    setup_tracing()
    yield


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    settings = get_settings()

    setup_logging(
        log_level=settings.log_level,
        json_output=not settings.debug,
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.4.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TraceIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-ID"],
    )

    # Routers
    app.include_router(health_router)
    app.include_router(repos_router)
    app.include_router(chat_router)
    app.include_router(agent_router)

    # OTEL instrumentation
    instrument_fastapi(app)

    return app


app = create_app()
