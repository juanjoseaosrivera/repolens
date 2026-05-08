"""Tests for the domain exception hierarchy."""

from repolens.errors import AgentError, IngestionError, RepoLensError, RetrievalError


def test_hierarchy():
    assert issubclass(IngestionError, RepoLensError)
    assert issubclass(RetrievalError, RepoLensError)
    assert issubclass(AgentError, RepoLensError)


def test_error_detail():
    err = RepoLensError("something broke", detail="extra context")
    assert str(err) == "something broke"
    assert err.detail == "extra context"
