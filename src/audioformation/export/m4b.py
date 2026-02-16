
"""
M4B Export — Create audiobook files with chapter markers and metadata.

Pipeline Node 8: Export (M4B variant).
Uses ffmpeg to concatenate chapters, encode to AAC, and embed ffmetadata.
"""

import subprocess
from pathlib import Path

from audioformation.project import get_project_path, load_project_json
from audioformation.audio.processor import get_duration


def export_project_m4b(
    project_id: str,
    output_path: Path,
    bitrate: int = 128,
) -> bool:
    """
    Export entire project as a single M4B audiobook.

    1. Gathers mixed files from 06_MIX/renders/
    2. Calculates timeline positions
    3. Generates FFMPEG metadata
    4. Concatenates and encodes
    """
    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    
    # Source directory (mixed audio)
    mix_dir = project_path / "06_MIX" / "renders"
    if not mix_dir.exists():
        return False

    # Filter valid chapter files (exclude chunks/temps)
    def _is_valid_chapter(f: Path) -> bool:
        return f.suffix == ".wav" and "_trimmed" not in f.name

    # Sort files naturally (assuming ch01, ch02 naming)
    chapter_files = sorted(
        [f for f in mix_dir.iterdir() if _is_valid_chapter(f)]
    )

    if not chapter_files:
        return False

    # Calculate durations and timeline
    chapters_metadata = []
    current_time_ms = 0
    
    # Prepare concat list for ffmpeg
    concat_list_path = project_path / "07_EXPORT" / "concat_list.txt"
    concat_list_path.parent.mkdir(parents=True, exist_ok=True)
    
    concat_content = []

    # Map file stems to chapter titles from project.json if available
    pj_chapters = {ch["id"]: ch.get("title", ch["id"]) for ch in pj.get("chapters", [])}

    for f in chapter_files:
        # FFMPEG concat format
        # Use forward slashes even on Windows for ffmpeg compatibility
        safe_path = str(f.absolute()).replace("\\", "/").replace("'", "'\\''")
        concat_content.append(f"file '{safe_path}'")
        
        duration_sec = get_duration(f)
        duration_ms = int(duration_sec * 1000)
        
        # Determine title
        # Try to match filename 'ch01' -> 'The Beginning'
        stem = f.stem
        title = pj_chapters.get(stem, stem.replace("_", " ").title())

        chapters_metadata.append({
            "title": title,
            "start": current_time_ms,
            "end": current_time_ms + duration_ms
        })
        
        current_time_ms += duration_ms

    concat_list_path.write_text("\n".join(concat_content), encoding="utf-8")

    # Generate FFMPEG metadata file
    meta_path = project_path / "07_EXPORT" / "metadata.txt"
    
    # Global metadata
    meta_info = pj.get("export", {}).get("metadata", {})
    
    ffmetadata = _generate_ffmetadata(
        chapters_metadata,
        title=project_id.replace("_", " ").title(),
        author=meta_info.get("author", ""),
        year=str(meta_info.get("year", "")),
        narrator=meta_info.get("narrator", "")
    )
    meta_path.write_text(ffmetadata, encoding="utf-8")

    # Check for cover art
    cover_path_rel = pj.get("export", {}).get("cover_art")
    cover_path = (project_path / cover_path_rel) if cover_path_rel else None
    has_cover = cover_path and cover_path.exists()

    # Build FFMPEG command
    # -f concat -safe 0 -i concat_list.txt  (Audio Input)
    # -i metadata.txt                       (Chapters)
    # -i cover.jpg                          (Cover Art, optional)
    # -map_metadata 1                       (Use metadata file)
    # -c:a aac -b:a 128k                    (Encode Audio)
    
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-f", "concat", "-safe", "0", "-i", str(concat_list_path),
        "-i", str(meta_path),
    ]

    map_args = ["-map", "0:a"]
    
    if has_cover:
        cmd.extend(["-i", str(cover_path)])
        # Map audio from input 0, video (cover) from input 2
        # (Input 1 is metadata, which doesn't need mapping stream-wise, just -map_metadata)
        map_args.extend(["-map", "2:v"])
        # Set cover art disposition
        cmd.extend(["-disposition:v", "attached_pic"])

    cmd.extend(map_args)
    
    # Metadata mapping
    cmd.extend(["-map_metadata", "1"])

    # Codec settings
    cmd.extend([
        "-c:a", "aac",
        "-b:a", f"{bitrate}k",
        "-c:v", "copy", # Copy cover art (don't re-encode jpeg)
        "-f", "mp4",    # M4B is technically MP4 container
        str(output_path)
    ])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=None # Encoding can take time
        )
        
        # Clean up temp files
        concat_list_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        
        if result.returncode != 0:
            # Log error?
            return False
            
        return True

    except Exception:
        return False


def export_project_m4b_auto(project_id: str, bitrate: int = 128) -> bool:
    """
    Export entire project as M4B with automatic output path.
    
    Finds mixed audio files and exports them as a single M4B file.
    Returns True on success.
    """
    from audioformation.project import get_project_path
    
    project_path = get_project_path(project_id)
    export_dir = project_path / "07_EXPORT" / "audiobook"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = export_dir / f"{project_id}.m4b"
    return export_project_m4b(project_id, output_file, bitrate)


def _generate_ffmetadata(chapters: list[dict], title: str, author: str, year: str, narrator: str) -> str:
    """Generate FFMPEG metadata format content."""
    lines = [";FFMETADATA1"]
    
    if title:
        lines.append(f"title={title}")
    if author:
        lines.append(f"artist={author}") # 'artist' usually maps to Author in audiobooks
        lines.append(f"album_artist={author}")
    if year:
        lines.append(f"date={year}")
    if narrator:
        lines.append(f"composer={narrator}") # Often used for narrator if no specific tag
        lines.append(f"performer={narrator}")

    lines.append("")

    for ch in chapters:
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000") # ms
        lines.append(f"START={ch['start']}")
        lines.append(f"END={ch['end']}")
        lines.append(f"title={ch['title']}")
        lines.append("")

    return "\n".join(lines)
