"""Walker behavior: gitignore, always-skip dirs, binary detection."""

from __future__ import annotations

from pathlib import Path

from repolens.ingest.walker import language_for, walk


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def test_walks_text_files_and_assigns_language(tmp_path: Path):
    _write(tmp_path / "a.py", "print('hi')")
    _write(tmp_path / "b.ts", "export const x = 1;")
    _write(tmp_path / "README.md", "# repo")

    result = {f.relative_path: f for f in walk(tmp_path)}

    assert set(result) == {"a.py", "b.ts", "README.md"}
    assert result["a.py"].language == "python"
    assert result["b.ts"].language == "typescript"
    assert result["README.md"].language == "markdown"


def test_skips_always_skip_dirs(tmp_path: Path):
    _write(tmp_path / "src" / "a.py", "x = 1")
    _write(tmp_path / "node_modules" / "pkg" / "index.js", "module.exports = {}")
    _write(tmp_path / ".venv" / "lib.py", "noop")
    _write(tmp_path / "__pycache__" / "x.cpython-312.pyc", "garbage")

    paths = {f.relative_path for f in walk(tmp_path)}

    assert paths == {"src/a.py"}


def test_respects_root_gitignore(tmp_path: Path):
    _write(tmp_path / ".gitignore", "secrets/\n*.log\n")
    _write(tmp_path / "main.py", "x = 1")
    _write(tmp_path / "secrets" / "key.txt", "shh")
    _write(tmp_path / "debug.log", "noisy")

    paths = {f.relative_path for f in walk(tmp_path)}

    assert paths == {"main.py", ".gitignore"}


def test_skips_binary_files(tmp_path: Path):
    _write(tmp_path / "ok.py", "x = 1")
    _write(tmp_path / "bin.dat", b"\x00\x01\x02hello")

    paths = {f.relative_path for f in walk(tmp_path)}

    assert paths == {"ok.py"}


def test_language_for_special_filenames(tmp_path: Path):
    assert language_for(tmp_path / "Dockerfile") == "dockerfile"
    assert language_for(tmp_path / "Makefile") == "makefile"
    assert language_for(tmp_path / "weird.unknown") is None
