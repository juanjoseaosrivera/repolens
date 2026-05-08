"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from repolens.api.app import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    return create_app()


@pytest.fixture
def client(app):
    """Synchronous test client for the FastAPI app."""
    return TestClient(app)
