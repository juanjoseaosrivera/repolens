"""Agent tools — search_code, query_graph, read_file.

Each tool is a LangChain-compatible tool that the LangGraph agent can invoke.
"""

import uuid
from pathlib import Path

from langchain_core.tools import tool


@tool
async def search_code(query: str, repository_id: str) -> str:
    """Search the codebase for relevant code snippets.

    Use this when the user asks about code functionality, where something is
    implemented, or how code works. Returns the most relevant code chunks
    with file paths and line numbers.

    Args:
        query: Natural language description of what to search for.
        repository_id: UUID of the repository to search in.
    """
    from repolens.api.deps import get_embedding_client, get_session_factory
    from repolens.retrieval.hybrid import hybrid_search
    from repolens.retrieval.reranker import get_reranker

    session_factory = get_session_factory()
    embedder = get_embedding_client()
    reranker = get_reranker()

    async with session_factory() as session:
        candidates = await hybrid_search(
            query,
            uuid.UUID(repository_id),
            session,
            embedder=embedder,
        )
        chunks = reranker.rerank(query, candidates)

    if not chunks:
        return "No relevant code found for this query."

    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[{i}] {c.file_path}:{c.start_line}-{c.end_line}\n"
            f"```{c.language or ''}\n{c.content}\n```"
        )
    return "\n\n".join(parts)


@tool
async def query_graph(question: str, repository_id: str) -> str:
    """Query the code dependency graph to find relationships between code elements.

    Use this for questions like "who calls function X", "what imports file Y",
    "what would break if I change Z", or "what does file W define".

    Args:
        question: Natural language question about code relationships.
        repository_id: UUID of the repository to query.
    """
    from repolens.graph import GraphQueryService, get_graph_client

    client = get_graph_client()
    service = GraphQueryService(client)
    repo_uuid = uuid.UUID(repository_id)

    question_lower = question.lower()

    # Route to the appropriate graph query based on the question
    if "call" in question_lower or "who calls" in question_lower:
        # Extract function name (last quoted or last word)
        func_name = _extract_name(question)
        nodes = await service.who_calls(func_name, repo_uuid)
        if not nodes:
            return f"No callers found for '{func_name}'."
        lines = [f"Functions that call '{func_name}':"]
        for n in nodes:
            lines.append(f"  - {n.name} in {n.file_path}")
        return "\n".join(lines)

    elif "import" in question_lower:
        file_path = _extract_name(question)
        nodes = await service.what_imports(file_path, repo_uuid)
        if not nodes:
            return f"No files import '{file_path}'."
        lines = [f"Files that import '{file_path}':"]
        for n in nodes:
            lines.append(f"  - {n.file_path}")
        return "\n".join(lines)

    elif "define" in question_lower or "what does" in question_lower:
        file_path = _extract_name(question)
        nodes = await service.what_does_file_define(file_path, repo_uuid)
        if not nodes:
            return f"No definitions found in '{file_path}'."
        lines = [f"Definitions in '{file_path}':"]
        for n in nodes:
            lines.append(f"  - [{n.label}] {n.name}")
        return "\n".join(lines)

    elif "impact" in question_lower or "break" in question_lower or "change" in question_lower:
        func_name = _extract_name(question)
        nodes = await service.impact_analysis(func_name, repo_uuid)
        if not nodes:
            return f"No transitive callers found for '{func_name}'."
        lines = [f"Impact analysis for '{func_name}' — these functions would be affected:"]
        for n in nodes:
            lines.append(f"  - {n.name} in {n.file_path}")
        return "\n".join(lines)

    else:
        # Fallback: try impact analysis
        func_name = _extract_name(question)
        nodes = await service.impact_analysis(func_name, repo_uuid)
        if nodes:
            lines = [f"Related functions for '{func_name}':"]
            for n in nodes:
                lines.append(f"  - {n.name} in {n.file_path}")
            return "\n".join(lines)
        return "Could not determine a specific graph query for this question."


@tool
async def read_file(file_path: str, repository_id: str) -> str:
    """Read the full content of a specific file from the repository.

    Use this when you need to see the complete file content, not just chunks.
    The file content is bounded to prevent excessive token usage.

    Args:
        file_path: Relative path of the file within the repository.
        repository_id: UUID of the repository.
    """
    from repolens.api.deps import get_session_factory
    from repolens.storage.models import Repository

    session_factory = get_session_factory()

    async with session_factory() as session:
        repo = await session.get(Repository, uuid.UUID(repository_id))
        if repo is None or repo.clone_path is None:
            return "Repository not found or not cloned."

        clone_path = Path(repo.clone_path)
        full_path = clone_path / file_path

        if not full_path.exists():
            return f"File not found: {file_path}"

        # Security: ensure path is within clone directory
        try:
            full_path.resolve().relative_to(clone_path.resolve())
        except ValueError:
            return "Access denied: path traversal detected."

        content = full_path.read_text(encoding="utf-8", errors="replace")

        # Bound the content to prevent excessive token usage
        max_lines = 200
        lines = content.splitlines()
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])
            content += f"\n\n... (truncated — {len(lines)} total lines, showing first {max_lines})"

        return f"File: {file_path}\n```\n{content}\n```"


def _extract_name(text: str) -> str:
    """Best-effort extraction of a function/file name from a natural language question."""
    import re

    # Look for quoted strings
    quoted: list[str] = re.findall(r"['\"`]([^'\"`]+)['\"`]", text)
    if quoted:
        return quoted[-1]

    # Look for backtick-wrapped
    backtick: list[str] = re.findall(r"`([^`]+)`", text)
    if backtick:
        return backtick[-1]

    # Fall back to last word that looks like a name (has underscore or dot)
    words = text.split()
    for word in reversed(words):
        cleaned = word.strip("?.,!;:")
        if "_" in cleaned or "." in cleaned:
            return cleaned

    # Last resort: last word
    return words[-1].strip("?.,!;:") if words else ""


# Tool list for the agent
AGENT_TOOLS = [search_code, query_graph, read_file]
