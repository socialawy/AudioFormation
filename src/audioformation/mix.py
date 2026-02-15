
"""
Mix pipeline node logic.

Iterates over processed chapters and mixes them with background music/SFX.
Calls the AudioMixer.
"""

import logging
from pathlib import Path
from typing import Any, Callable

from audioformation.audio.mixer import AudioMixer
from audioformation.project import (
    get_project_path,
    load_project_json,
)
from audioformation.pipeline import update_node_status

logger = logging.getLogger(__name__)


def mix_project(
    project_id: str,
    music_file: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> bool:
    """
    Run the mixing stage for a project.

    Args:
        project_id: Project identifier.
        music_file: Optional filename in 05_MUSIC/generated to use as background.
                    If None, tries to find the most recent generated music.
        progress_callback: Optional function to receive status messages.

    Returns:
        True if all chapters mixed successfully.
    """
    def _notify(msg: str, level: str = "info") -> None:
        if level == "error":
            logger.error(msg)
        elif level == "warning":
            logger.warning(msg)
        else:
            logger.info(msg)
        
        if progress_callback:
            progress_callback(msg)

    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    mix_config = pj.get("mix", {})

    # Initialize mixer
    mixer = AudioMixer(mix_config)

    # Paths
    processed_dir = project_path / "03_GENERATED" / "processed"
    mix_dir = project_path / "06_MIX" / "renders"
    music_dir = project_path / "05_MUSIC" / "generated"
    
    mix_dir.mkdir(parents=True, exist_ok=True)

    # Determine background music path
    bg_music_path: Path | None = None
    if music_file:
        bg_music_path = music_dir / music_file
        if not bg_music_path.exists():
            _notify(f"⚠ Music file not found: {music_file}", "warning")
            bg_music_path = None
    else:
        # Auto-detect latest music
        if music_dir.exists():
            candidates = sorted(music_dir.glob("*.wav"), key=lambda f: f.stat().st_mtime, reverse=True)
            if candidates:
                bg_music_path = candidates[0]
                _notify(f"  Using background music: {bg_music_path.name}")
            else:
                _notify("  No background music found. Mixing voice only.")
        else:
             _notify("  No music directory found. Mixing voice only.")

    # Find processed chapters
    def _is_chunk_file(f: Path) -> bool:
        if "_" not in f.stem:
            return False
        parts = f.stem.rsplit("_", 1)
        return len(parts) == 2 and parts[1].isdigit()

    chapter_files = []
    if processed_dir.exists():
        chapter_files = sorted(
            f for f in processed_dir.glob("ch*.wav")
            if not _is_chunk_file(f)
        )

    if not chapter_files:
        # Fallback to raw if processed missing
        raw_dir = project_path / "03_GENERATED" / "raw"
        if raw_dir.exists():
            chapter_files = sorted(
                f for f in raw_dir.glob("ch*.wav")
                if not _is_chunk_file(f)
            )
        
        if chapter_files:
            _notify("⚠ Using RAW audio (process step skipped?)", "warning")
        else:
            _notify("✗ No chapter audio found to mix.", "error")
            return False

    update_node_status(project_id, "mix", "running")

    success_count = 0
    _notify(f"Mixing {len(chapter_files)} chapters...")

    for voice_path in chapter_files:
        output_path = mix_dir / voice_path.name
        
        _notify(f"  Mixing {voice_path.name}...")
        ok = mixer.mix_chapter(voice_path, bg_music_path, output_path)
        
        if ok:
            success_count += 1
        else:
            _notify(f"  ✗ Failed to mix {voice_path.name}", "error")

    if success_count == len(chapter_files):
        update_node_status(project_id, "mix", "complete")
        _notify("✓ Mixing complete.")
        return True
    else:
        update_node_status(project_id, "mix", "partial")
        _notify(f"⚠ Mixed {success_count}/{len(chapter_files)} chapters.", "warning")
        return False