"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from repolens.api.chat import router as chat_router
from repolens.api.health import router as health_router
from repolens.api.repos import router as repos_router
from repolens.config import get_settings
from repolens.observability.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: set up and tear down shared resources."""
    # Engine/session factory are created lazily in deps.py on first request.
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
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(repos_router)
    app.include_router(chat_router)

    return app


app = create_app()
