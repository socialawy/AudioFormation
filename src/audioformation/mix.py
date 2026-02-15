
"""
Mix pipeline node logic.

Iterates over processed chapters and mixes them with background music/SFX.
Calls the AudioMixer.
"""

import click
from pathlib import Path
from typing import Any

from audioformation.audio.mixer import AudioMixer
from audioformation.project import (
    get_project_path,
    load_project_json,
)
from audioformation.pipeline import update_node_status


def mix_project(
    project_id: str,
    music_file: str | None = None,
) -> bool:
    """
    Run the mixing stage for a project.

    Args:
        project_id: Project identifier.
        music_file: Optional filename in 05_MUSIC/generated to use as background.
                    If None, tries to find the most recent generated music.

    Returns:
        True if all chapters mixed successfully.
    """
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
            click.secho(f"⚠ Music file not found: {music_file}", fg="yellow")
            bg_music_path = None
    else:
        # Auto-detect latest music
        candidates = sorted(music_dir.glob("*.wav"), key=lambda f: f.stat().st_mtime, reverse=True)
        if candidates:
            bg_music_path = candidates[0]
            click.echo(f"  Using background music: {bg_music_path.name}")
        else:
            click.echo("  No background music found. Mixing voice only.")

    # Find processed chapters
    # Exclude chunks, look for stitched chapters (e.g. ch01.wav, ch01_title.wav)
    # Similar logic to export command
    def _is_chunk_file(f: Path) -> bool:
        if "_" not in f.stem:
            return False
        parts = f.stem.rsplit("_", 1)
        return len(parts) == 2 and parts[1].isdigit()

    chapter_files = sorted(
        f for f in processed_dir.glob("ch*.wav")
        if not _is_chunk_file(f)
    )

    if not chapter_files:
        # Fallback to raw if processed missing?
        # Ideally mix strictly follows process.
        raw_dir = project_path / "03_GENERATED" / "raw"
        chapter_files = sorted(
            f for f in raw_dir.glob("ch*.wav")
            if not _is_chunk_file(f)
        )
        if chapter_files:
            click.secho("⚠ Using RAW audio (process step skipped?)", fg="yellow")
        else:
            click.secho("✗ No chapter audio found to mix.", fg="red")
            return False

    update_node_status(project_id, "mix", "running")

    success_count = 0
    click.echo(f"Mixing {len(chapter_files)} chapters...")

    for voice_path in chapter_files:
        output_path = mix_dir / voice_path.name
        
        click.echo(f"  Mixing {voice_path.name}...")
        ok = mixer.mix_chapter(voice_path, bg_music_path, output_path)
        
        if ok:
            success_count += 1
        else:
            click.secho(f"  ✗ Failed to mix {voice_path.name}", fg="red")

    if success_count == len(chapter_files):
        update_node_status(project_id, "mix", "complete")
        click.secho("✓ Mixing complete.", fg="green", bold=True)
        return True
    else:
        update_node_status(project_id, "mix", "partial")
        click.secho(f"⚠ Mixed {success_count}/{len(chapter_files)} chapters.", fg="yellow")
        return False
