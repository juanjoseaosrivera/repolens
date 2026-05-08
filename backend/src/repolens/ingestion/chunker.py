"""Naive line-based chunker.

Phase 1: splits files into overlapping chunks by line count.
Phase 2 will replace this with AST-aware chunking via tree-sitter.
"""

from dataclasses import dataclass

from repolens.config import get_settings


@dataclass(frozen=True, slots=True)
class RawChunk:
    """A chunk of source code before embedding."""

    content: str
    start_line: int
    end_line: int


def chunk_file(
    content: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[RawChunk]:
    """Split *content* into overlapping line-based chunks.

    Args:
        content: Full file text.
        chunk_size: Lines per chunk (default from settings).
        overlap: Lines of overlap between consecutive chunks (default from settings).

    Returns:
        A list of ``RawChunk`` objects. Empty files yield an empty list.
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    lines = content.splitlines(keepends=True)
    if not lines:
        return []

    step = max(chunk_size - overlap, 1)
    chunks: list[RawChunk] = []

    for start in range(0, len(lines), step):
        end = min(start + chunk_size, len(lines))
        chunk_text = "".join(lines[start:end])
        if chunk_text.strip():
            chunks.append(
                RawChunk(
                    content=chunk_text,
                    start_line=start + 1,  # 1-indexed
                    end_line=end,
                )
            )
        if end == len(lines):
            break

    return chunks
