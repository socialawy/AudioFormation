"""
Export metadata — checksums, manifest generation.

The manifest.json tracks every exported file with SHA256 checksums
for integrity verification.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(
    export_dir: Path,
    project_id: str,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """
    Generate manifest.json with SHA256 checksums for all exported files.

    Args:
        export_dir: Directory containing exported files.
        project_id: Project identifier.
        metadata: Optional export metadata (author, title, etc.).

    Returns path to the manifest file.
    """
    files: list[dict[str, Any]] = []

    for path in sorted(export_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files.append({
                "path": str(path.relative_to(export_dir)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })

    manifest = {
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(files),
        "metadata": metadata or {},
        "files": files,
    }

    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return manifest_path