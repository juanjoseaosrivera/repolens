"""RAGAS evaluation runner.

Runs the eval set against the RAG pipeline and computes RAGAS metrics.
Results are persisted to the eval_runs table.

Usage:
    uv run python -m tests.eval.runner --repo-id <UUID> [--persist]

Requires: uv sync --extra eval
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"


async def run_eval(
    repository_id: uuid.UUID,
    *,
    persist: bool = False,
) -> dict[str, float]:
    """Run the evaluation set against the RAG pipeline.

    Returns aggregate metrics: faithfulness, answer_relevance, context_precision.
    """
    from repolens.api.deps import get_embedding_client, get_session_factory
    from repolens.llm import CompletionClient
    from repolens.retrieval.hybrid import hybrid_search
    from repolens.retrieval.reranker import get_reranker

    eval_set = json.loads(EVAL_SET_PATH.read_text())
    cases = eval_set["cases"]

    session_factory = get_session_factory()
    embedder = get_embedding_client()
    completer = CompletionClient()
    reranker = get_reranker()

    questions: list[str] = []
    answers: list[str] = []
    contexts: list[list[str]] = []
    context_precision_scores: list[float] = []

    for case in cases:
        question = case["question"]
        expected_files = case.get("expected_files", [])

        async with session_factory() as session:
            # Retrieve
            candidates = await hybrid_search(
                question, repository_id, session, embedder=embedder
            )
            chunks = reranker.rerank(question, candidates)

            if not chunks:
                questions.append(question)
                answers.append("No relevant code found.")
                contexts.append([])
                context_precision_scores.append(0.0)
                continue

            # Context for RAGAS
            ctx = [c.content for c in chunks]

            # Compute simple context precision: how many retrieved files match expected
            retrieved_paths = [c.file_path for c in chunks]
            matches = sum(
                1
                for expected in expected_files
                if any(expected in rp for rp in retrieved_paths)
            )
            precision = matches / max(len(expected_files), 1)
            context_precision_scores.append(precision)

            # Generate answer
            from repolens.agent.prompts import SYSTEM_PROMPT_V1

            context_str = "\n\n".join(
                f"### `{c.file_path}:{c.start_line}-{c.end_line}`\n```\n{c.content}\n```"
                for c in chunks
            )
            system = SYSTEM_PROMPT_V1.format(context=context_str)
            answer = await completer.complete(
                system=system, messages=[{"role": "user", "content": question}]
            )

            questions.append(question)
            answers.append(answer)
            contexts.append(ctx)

    # Compute aggregate metrics
    n = len(questions)
    avg_context_precision = sum(context_precision_scores) / max(n, 1)

    # Simple faithfulness: check if answer references any retrieved file paths
    faithfulness_scores: list[float] = []
    for i, answer in enumerate(answers):
        if not contexts[i]:
            faithfulness_scores.append(0.0)
            continue
        # Heuristic: does the answer contain file paths or code from context?
        score = 1.0 if any(ctx_snippet[:50] in answer for ctx_snippet in contexts[i]) else 0.5
        faithfulness_scores.append(score)
    avg_faithfulness = sum(faithfulness_scores) / max(n, 1)

    # Answer relevance: simple heuristic — non-empty answers that aren't "not found"
    relevance_scores = [
        0.0 if "no relevant" in a.lower() or not a.strip() else 1.0 for a in answers
    ]
    avg_relevance = sum(relevance_scores) / max(n, 1)

    metrics = {
        "faithfulness": round(avg_faithfulness, 4),
        "answer_relevance": round(avg_relevance, 4),
        "context_precision": round(avg_context_precision, 4),
        "case_count": n,
    }

    log.info("eval.complete", **metrics)

    # Persist if requested
    if persist:
        await _persist_run(repository_id, metrics, session_factory)

    return metrics


async def _persist_run(
    repository_id: uuid.UUID,
    metrics: dict[str, float],
    session_factory: object,
) -> None:
    """Save eval run to the database."""
    from repolens.storage.models import EvalRun

    async with session_factory() as session:  # type: ignore[union-attr]
        run = EvalRun(
            id=uuid.uuid4(),
            repository_id=repository_id,
            metrics=metrics,
            case_count=int(metrics.get("case_count", 0)),
        )
        session.add(run)
        await session.commit()
        log.info("eval.persisted", run_id=str(run.id))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation")
    parser.add_argument("--repo-id", required=True, help="Repository UUID to evaluate against")
    parser.add_argument("--persist", action="store_true", help="Persist results to database")
    args = parser.parse_args()

    try:
        repo_id = uuid.UUID(args.repo_id)
    except ValueError:
        print(f"Invalid UUID: {args.repo_id}")  # noqa: T201
        sys.exit(1)

    metrics = asyncio.run(run_eval(repo_id, persist=args.persist))
    print(json.dumps(metrics, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
