"""Sensitive-content filter for ingestion.

Skips files that likely contain secrets (.env, credentials, key files)
and redacts patterns that look like API keys or tokens from chunk content.
"""

import re
from pathlib import PurePosixPath

import structlog

log = structlog.get_logger(__name__)

# Files to skip entirely during ingestion
SENSITIVE_FILE_PATTERNS: set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    ".env.development",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
}

SENSITIVE_DIR_PATTERNS: set[str] = {
    ".ssh",
    ".gnupg",
    "secrets",
}

# Regex patterns for things that look like secrets in content
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # API keys: sk-..., sk-ant-..., AKIA..., etc.
    re.compile(r"(?:sk-[a-zA-Z0-9\-]{20,})", re.ASCII),
    re.compile(r"(?:sk-ant-[a-zA-Z0-9\-]{20,})", re.ASCII),
    re.compile(r"(?:AKIA[A-Z0-9]{16})", re.ASCII),
    # Generic long hex/base64 tokens after common prefixes
    re.compile(
        r"(?:api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?token|secret[_-]?key)"
        r"\s*[:=]\s*['\"]?([a-zA-Z0-9\-_./+]{20,})['\"]?",
        re.IGNORECASE,
    ),
    # Bearer tokens
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_./+]{20,}", re.ASCII),
    # Private key blocks
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", re.ASCII),
]

_REDACTION = "[REDACTED]"


def should_skip_file(relative_path: str) -> bool:
    """Return True if the file should be excluded from ingestion."""
    path = PurePosixPath(relative_path)

    # Check filename
    if path.name in SENSITIVE_FILE_PATTERNS:
        log.info("filter.skip_sensitive_file", path=relative_path)
        return True

    # Check suffix
    if path.suffix in {".pem", ".key", ".p12", ".pfx", ".keystore"}:
        log.info("filter.skip_sensitive_extension", path=relative_path)
        return True

    # Check directory components
    for part in path.parts:
        if part in SENSITIVE_DIR_PATTERNS:
            log.info("filter.skip_sensitive_dir", path=relative_path)
            return True

    return False


def redact_secrets(content: str) -> str:
    """Replace likely secret values in *content* with a redaction placeholder."""
    result = content
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(_REDACTION, result)
    return result
