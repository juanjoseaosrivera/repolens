"""Naive recursive chunker: size cap, overlap, offset accuracy."""

from __future__ import annotations

import pytest

from repolens.ingest.chunker_naive import chunk_text


def test_empty_text_yields_no_chunks():
    assert chunk_text("") == []


def test_short_text_returns_single_chunk():
    chunks = chunk_text("hello world", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len("hello world")


def test_offsets_reconstruct_the_source():
    text = "alpha\n\nbeta\n\ngamma\n\ndelta\n\nepsilon"
    chunks = chunk_text(text, chunk_size=12, overlap=0)
    # With overlap=0 every char appears in exactly one chunk and reassembles.
    assert "".join(c.text for c in chunks) == text
    for c in chunks:
        assert text[c.start_char : c.end_char] == c.text


def test_chunk_size_is_a_soft_cap():
    text = "a" * 50 + "\n\n" + "b" * 50
    chunks = chunk_text(text, chunk_size=40, overlap=0)
    # Each side exceeds the cap but has no further separator beyond ""; the
    # character fallback splits them into <=40 char pieces.
    assert all(len(c.text) <= 40 for c in chunks)


def test_overlap_repeats_tail_into_next_chunk():
    text = "para1.\n\npara2.\n\npara3.\n\npara4."
    chunks = chunk_text(text, chunk_size=14, overlap=8)
    assert len(chunks) >= 2
    # Adjacent chunks should share a non-empty suffix/prefix.
    overlap_text = chunks[0].text[-8:]
    assert overlap_text in chunks[1].text


def test_invalid_args():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, overlap=-1)
