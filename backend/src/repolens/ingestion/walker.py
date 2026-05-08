"""Directory walker — yields source files from a cloned repository.

Skips binary files, hidden directories, and common non-source artefacts.
"""

import mimetypes
from collections.abc import Iterator
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

SKIP_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".angular",
    "target",
    "coverage",
}

SKIP_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".so",
    ".o",
    ".a",
    ".dylib",
    ".dll",
    ".exe",
    ".class",
    ".jar",
    ".whl",
    ".egg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".wav",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".pdf",
    ".db",
    ".sqlite",
    ".sqlite3",
}

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
}

MAX_FILE_SIZE_BYTES = 512 * 1024  # skip files > 512 KiB


def walk_repo(repo_path: Path) -> Iterator[tuple[str, str, str | None]]:
    """Yield ``(relative_path, content, language)`` for each source file.

    Files that are binary, too large, or in skip-listed directories are
    silently skipped.
    """
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue

        # Skip hidden files
        if any(part.startswith(".") and part != "." for part in path.relative_to(repo_path).parts):
            if not path.relative_to(repo_path).parts[0] == ".github":
                continue

        # Skip directories
        rel_parts = set(path.relative_to(repo_path).parts)
        if rel_parts & SKIP_DIRS:
            continue

        # Skip by extension
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue

        # Skip large files
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            log.debug("walker.skip_large", path=str(path))
            continue

        # Skip binary-looking files via mimetype heuristic
        mime, _ = mimetypes.guess_type(str(path))
        if mime and not mime.startswith("text") and mime != "application/json":
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log.warning("walker.read_error", path=str(path))
            continue

        if not content.strip():
            continue

        rel = str(path.relative_to(repo_path))
        language = EXTENSION_TO_LANGUAGE.get(path.suffix.lower())
        yield rel, content, language
