"""Tests for settings module."""

from repolens.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.app_name == "RepoLens"
    assert settings.embedding_dimensions == 1536
    assert settings.default_model == "claude-sonnet-4-6"
    assert "localhost" in settings.database_url
