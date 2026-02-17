"""
Input sanitization and path safety.

Threat model (v1.0):
- Path traversal from user input (project IDs, file paths)
- Injection in filenames (chapter names → file system)
- API key exposure in version control
- Malformed project.json causing crashes
"""

import re
from pathlib import Path
from typing import Any

# Project IDs: alphanumeric, underscore, hyphen only
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Filenames: strip anything dangerous
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_project_id(raw: str) -> str:
    """
    Sanitize a project ID to filesystem-safe characters.

    Replaces spaces with underscores, strips unsafe characters,
    converts to uppercase.

    Raises ValueError if result is empty.
    """
    cleaned = raw.strip().replace(" ", "_").upper()
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)

    if not cleaned:
        raise ValueError(f"Project ID '{raw}' contains no valid characters.")

    if not _PROJECT_ID_RE.match(cleaned):
        raise ValueError(f"Project ID '{cleaned}' is invalid after sanitization.")

    return cleaned


def sanitize_filename(raw: str) -> str:
    """
    Sanitize a filename, stripping path separators, null bytes,
    and other dangerous characters.

    Raises ValueError if result is empty.
    """
    # Remove path components — only the filename part
    name = Path(raw).name

    # Strip unsafe characters
    name = _UNSAFE_FILENAME_CHARS.sub("", name)

    # No leading dots (hidden files / directory traversal)
    name = name.lstrip(".")

    if not name:
        raise ValueError(f"Filename '{raw}' is empty after sanitization.")

    return name


def validate_path_within(path: Path, root: Path) -> bool:
    """
    Ensure `path` resolves to a location within `root`.

    Prevents directory traversal attacks.
    """
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        return resolved == root_resolved or root_resolved in resolved.parents
    except (OSError, ValueError):
        return False


def redact_api_keys(config: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of config with API key values redacted for logging.

    Matches keys containing 'key', 'secret', 'token', 'password' (case-insensitive).
    """
    sensitive_patterns = {"key", "secret", "token", "password"}

    def _redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if any(p in k.lower() for p in sensitive_patterns) and isinstance(
                    v, str
                ):
                    result[k] = "***REDACTED***"
                else:
                    result[k] = _redact(v)
            return result
        if isinstance(obj, list):
            return [_redact(item) for item in obj]
        return obj

    return _redact(config)
