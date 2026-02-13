"""
Text ingestion — import text files into a project, detect encoding,
assign languages, prepare for generation.

Pipeline Node 1: Ingest.
"""

import shutil
from pathlib import Path
from typing import Any

from audioformation.project import (
    get_project_path,
    load_project_json,
    save_project_json,
)
from audioformation.pipeline import update_node_status
from audioformation.utils.arabic import is_arabic, classify_diacritization
from audioformation.utils.security import sanitize_filename


def ingest_text(
    project_id: str,
    source_dir: Path,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Import text files from source_dir into the project.

    Steps:
    1. Copy .txt files to 01_TEXT/chapters/
    2. Auto-detect language per file (ar/en)
    3. Create chapter entries in project.json
    4. Detect Arabic diacritization level
    5. Update pipeline status

    Args:
        project_id: Target project.
        source_dir: Directory containing .txt files.
        language: Override language for all files (None = auto-detect).

    Returns dict with ingestion results.
    """
    project_path = get_project_path(project_id)
    chapters_dir = project_path / "01_TEXT" / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    # Find all .txt files
    txt_files = sorted(source_dir.glob("*.txt"))
    if not txt_files:
        raise ValueError(f"No .txt files found in {source_dir}")

    pj = load_project_json(project_id)
    existing_ids = set(ch["id"] for ch in pj.get("chapters", []))
    new_chapters: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for i, src_file in enumerate(txt_files, start=1):
        safe_name = sanitize_filename(src_file.name)
        dst_file = chapters_dir / safe_name

        # Copy file
        shutil.copy2(src_file, dst_file)

        # Read content
        content = dst_file.read_text(encoding="utf-8").strip()

        # Detect language
        if language:
            detected_lang = language
        else:
            detected_lang = "ar" if is_arabic(content) else "en"

        # Generate chapter ID from filename
        ch_id = safe_name.replace(".txt", "").replace(" ", "_").lower()

        # Check diacritization for Arabic
        diacrit_info = None
        if detected_lang == "ar":
            diacrit_info = classify_diacritization(content)

        # Skip if already exists
        if ch_id in existing_ids:
            results.append({
                "file": safe_name,
                "chapter_id": ch_id,
                "status": "skipped",
                "reason": "Already exists in project.json",
            })
            continue

        # Create chapter entry
        chapter_entry: dict[str, Any] = {
            "id": ch_id,
            "title": ch_id.replace("_", " ").title(),
            "language": detected_lang,
            "source": f"01_TEXT/chapters/{safe_name}",
            "character": "narrator",
            "mode": "single",
            "direction": {
                "energy": "normal",
                "pace": "moderate",
                "emotion": "neutral",
            },
        }

        new_chapters.append(chapter_entry)
        results.append({
            "file": safe_name,
            "chapter_id": ch_id,
            "status": "ingested",
            "language": detected_lang,
            "characters": len(content),
            "diacritization": diacrit_info,
        })

    # Update project.json
    if new_chapters:
        pj.setdefault("chapters", []).extend(new_chapters)
        save_project_json(project_id, pj)

    # Update pipeline status
    update_node_status(
        project_id, "ingest", "complete",
        files_ingested=len([r for r in results if r["status"] == "ingested"]),
        files_skipped=len([r for r in results if r["status"] == "skipped"]),
    )

    return {
        "total_files": len(txt_files),
        "ingested": len([r for r in results if r["status"] == "ingested"]),
        "skipped": len([r for r in results if r["status"] == "skipped"]),
        "details": results,
    }