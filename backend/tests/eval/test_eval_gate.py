"""CI eval gate — checks that eval metrics meet minimum thresholds.

This test is skipped when REPOLENS_EVAL_REPO_ID is not set (no ingested repo
available). In CI, set this env var to run the eval gate against a pre-ingested
repository.

Usage in CI:
    REPOLENS_EVAL_REPO_ID=<uuid> uv run pytest tests/eval/ -v
"""

import os
import uuid

import pytest

EVAL_REPO_ID = os.environ.get("REPOLENS_EVAL_REPO_ID")

# Minimum thresholds (Phase 2 targets from progress-tracker.md)
MIN_FAITHFULNESS = 0.85
MIN_ANSWER_RELEVANCE = 0.80
MIN_CONTEXT_PRECISION = 0.75


@pytest.mark.skipif(
    EVAL_REPO_ID is None,
    reason="REPOLENS_EVAL_REPO_ID not set — skipping eval gate",
)
async def test_eval_metrics_meet_thresholds() -> None:
    """Run the eval set and assert metrics meet Phase 2 targets."""
    from tests.eval.runner import run_eval

    repo_id = uuid.UUID(EVAL_REPO_ID)  # type: ignore[arg-type]
    metrics = await run_eval(repo_id, persist=True)

    assert metrics["faithfulness"] >= MIN_FAITHFULNESS, (
        f"Faithfulness {metrics['faithfulness']:.4f} < {MIN_FAITHFULNESS}"
    )
    assert metrics["answer_relevance"] >= MIN_ANSWER_RELEVANCE, (
        f"Answer relevance {metrics['answer_relevance']:.4f} < {MIN_ANSWER_RELEVANCE}"
    )
    assert metrics["context_precision"] >= MIN_CONTEXT_PRECISION, (
        f"Context precision {metrics['context_precision']:.4f} < {MIN_CONTEXT_PRECISION}"
    )
