"""Recursive character splitter — deliberately naive (Phase 1)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200

# Tried in order. The first separator that yields a piece <= chunk_size wins
# for that piece; otherwise we recurse with the next-finer separator. The empty
# string is the unconditional fallback (character-level slicing).
DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", " ", "")


@dataclass(frozen=True, slots=True)
class TextChunk:
    text: str
    start_char: int
    end_char: int


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    separators: tuple[str, ...] = DEFAULT_SEPARATORS,
) -> list[TextChunk]:
    """Split `text` into overlapping chunks, biased toward natural boundaries.

    `chunk_size` is a soft cap; a single token longer than `chunk_size` is left
    intact rather than split mid-word. `overlap` is applied during merge.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")
    if not text:
        return []

    pieces = list(_split_recursive(text, 0, chunk_size, separators))
    return _merge_with_overlap(pieces, chunk_size, overlap)


def _split_recursive(
    text: str,
    base_offset: int,
    chunk_size: int,
    separators: tuple[str, ...],
) -> Iterator[TextChunk]:
    if len(text) <= chunk_size or not separators:
        if text:
            yield TextChunk(text=text, start_char=base_offset, end_char=base_offset + len(text))
        return

    sep, *rest = separators
    if sep == "":
        # Hard fallback: slice on character boundaries.
        for i in range(0, len(text), chunk_size):
            piece = text[i : i + chunk_size]
            yield TextChunk(
                text=piece,
                start_char=base_offset + i,
                end_char=base_offset + i + len(piece),
            )
        return

    cursor = 0
    parts = text.split(sep)
    for idx, part in enumerate(parts):
        is_last = idx == len(parts) - 1
        # Reattach the separator to non-last parts so offsets stay accurate.
        attached = part if is_last else part + sep
        if not attached:
            cursor += len(attached)
            continue
        if len(attached) <= chunk_size:
            yield TextChunk(
                text=attached,
                start_char=base_offset + cursor,
                end_char=base_offset + cursor + len(attached),
            )
        else:
            yield from _split_recursive(attached, base_offset + cursor, chunk_size, tuple(rest))
        cursor += len(attached)


def _merge_with_overlap(pieces: list[TextChunk], chunk_size: int, overlap: int) -> list[TextChunk]:
    if not pieces:
        return []

    merged: list[TextChunk] = []
    buf: list[TextChunk] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        merged.append(
            TextChunk(
                text="".join(p.text for p in buf),
                start_char=buf[0].start_char,
                end_char=buf[-1].end_char,
            )
        )
        # Build overlap tail: keep trailing pieces that fit within `overlap`.
        if overlap == 0:
            buf = []
            buf_len = 0
            return
        tail: list[TextChunk] = []
        tail_len = 0
        for p in reversed(buf):
            if tail_len + len(p.text) > overlap:
                break
            tail.insert(0, p)
            tail_len += len(p.text)
        buf = tail
        buf_len = tail_len

    for piece in pieces:
        if buf_len + len(piece.text) > chunk_size and buf:
            flush()
        buf.append(piece)
        buf_len += len(piece.text)

    flush()
    return merged
