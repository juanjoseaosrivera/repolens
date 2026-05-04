"""Walk a repository, respecting .gitignore, skipping binaries and vendored dirs."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pathspec
from pathspec.pattern import Pattern

# Directories we always skip even if not in .gitignore — they bloat ingestion
# without adding value.
ALWAYS_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".next",
        ".idea",
        ".vscode",
    }
)

MAX_FILE_BYTES = 1_000_000  # 1 MB — anything bigger is almost certainly generated.

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".m": "objc",
    ".mm": "objcpp",
    ".swift": "swift",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".md": "markdown",
    ".rst": "rst",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".ini": "ini",
    ".xml": "xml",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
}


@dataclass(frozen=True, slots=True)
class WalkedFile:
    relative_path: str
    content: str
    language: str | None


def language_for(path: Path) -> str | None:
    if path.name.lower() == "dockerfile":
        return "dockerfile"
    if path.name.lower() == "makefile":
        return "makefile"
    return EXTENSION_TO_LANGUAGE.get(path.suffix.lower())


def _load_gitignore(root: Path) -> pathspec.PathSpec[Pattern]:
    """Build a single PathSpec from the repo's root .gitignore (if any).

    Nested .gitignore handling is intentionally out of scope for the MVP — the
    root file plus ALWAYS_SKIP_DIRS catches the long tail in practice.
    """
    patterns: list[str] = []
    root_ignore = root / ".gitignore"
    if root_ignore.is_file():
        patterns.extend(root_ignore.read_text(encoding="utf-8").splitlines())
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def _is_probably_text(path: Path, sample_bytes: int = 4096) -> bool:
    """Cheap binary detector: NUL byte in the first 4KB → binary."""
    try:
        with path.open("rb") as f:
            sample = f.read(sample_bytes)
    except OSError:
        return False
    return b"\x00" not in sample


def walk(root: str | Path) -> Iterator[WalkedFile]:
    """Yield text files under `root`, respecting .gitignore and skipping binaries.

    Paths in the result are relative to `root` and use forward slashes.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"{root_path} is not a directory")

    spec = _load_gitignore(root_path)

    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue

        relative = path.relative_to(root_path)
        rel_posix = relative.as_posix()

        if any(part in ALWAYS_SKIP_DIRS for part in relative.parts):
            continue
        if spec.match_file(rel_posix):
            continue

        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue

        if not _is_probably_text(path):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        yield WalkedFile(
            relative_path=rel_posix,
            content=content,
            language=language_for(path),
        )
