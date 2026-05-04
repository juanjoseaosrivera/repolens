"""`repolens` CLI: ingest a local repo and ask questions against it."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.chat.answer import answer as run_answer
from repolens.ingest.pipeline import ingest_repo

app = typer.Typer(no_args_is_help=True, add_completion=False, help="RepoLens CLI.")

# Module-level Typer parameters (B008-friendly).
_ARG_REPO_PATH = typer.Argument(..., exists=True, file_okay=False, dir_okay=True)
_OPT_NAME = typer.Option(None, "--name", "-n", help="Override repo name (default: dir name).")
_OPT_BATCH = typer.Option(64, "--batch-size", "-b", help="Embedding batch size.")
_ARG_QUESTION = typer.Argument(...)
_OPT_TOP_K = typer.Option(5, "--top-k", "-k")
_OPT_REPO = typer.Option(None, "--repo", "-r", help="Restrict to a repo name.")


@app.command()
def ingest(
    repo_path: Path = _ARG_REPO_PATH,
    name: str | None = _OPT_NAME,
    batch_size: int = _OPT_BATCH,
) -> None:
    """Ingest a local repo into Postgres."""
    typer.echo(f"Ingesting {repo_path}...")
    stats = ingest_repo(repo_path, name=name, batch_size=batch_size)
    typer.echo(
        f"Done. repo_id={stats.repo_id} files={stats.files_seen} chunks={stats.chunks_written}"
    )


@app.command()
def ask(
    question: str = _ARG_QUESTION,
    top_k: int = _OPT_TOP_K,
    repo: str | None = _OPT_REPO,
) -> None:
    """Answer a question using retrieved chunks from the ingested repos."""
    result = run_answer(question, top_k=top_k, repo_name=repo)

    typer.echo("\n=== Retrieved chunks ===")
    if not result.retrieved:
        typer.echo("(none)")
    for c in result.retrieved:
        typer.echo(
            f"  {c.file_path} (chunk {c.chunk_index}, score={c.score:.3f}, "
            f"lang={c.language or '?'}, repo={c.repo_name})"
        )

    typer.echo("\n=== Answer ===")
    typer.echo(result.text)

    typer.echo("\n=== Tokens ===")
    typer.echo(f"in={result.llm.input_tokens}  out={result.llm.output_tokens}")


if __name__ == "__main__":
    app()
