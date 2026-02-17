"""
MP3 export via pydub + ffmpeg.

Phase 1 export format. Simple, reliable, universal.
"""

from pathlib import Path

from pydub import AudioSegment


def export_mp3(
    input_path: Path,
    output_path: Path,
    bitrate: int = 192,
) -> bool:
    """
    Export an audio file as MP3.

    Args:
        input_path: Source audio file (WAV, FLAC, etc.).
        output_path: Destination MP3 path.
        bitrate: MP3 bitrate in kbps.

    Returns True on success.
    """
    try:
        audio = AudioSegment.from_file(str(input_path))
        audio.export(
            str(output_path),
            format="mp3",
            bitrate=f"{bitrate}k",
        )
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception:
        return False


def export_wav(
    input_path: Path,
    output_path: Path,
) -> bool:
    """
    Export / convert audio file to WAV format.

    Returns True on success.
    """
    try:
        audio = AudioSegment.from_file(str(input_path))
        audio.export(str(output_path), format="wav")
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception:
        return False


def export_project_mp3(project_id: str, bitrate: int = 192) -> bool:
    """
    Export an entire project as MP3.

    Finds the mixed audio file and exports it as MP3.
    Returns True on success.
    """
    from audioformation.project import get_project_path

    project_path = get_project_path(project_id)
    mix_dir = project_path / "06_MIX"
    export_dir = project_path / "07_EXPORT" / "audiobook"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Find the mixed file
    mixed_file = mix_dir / f"{project_id}_mixed.wav"
    if not mixed_file.exists():
        mixed_file = mix_dir / f"{project_id}.wav"

    if not mixed_file.exists():
        return False

    output_file = export_dir / f"{project_id}.mp3"
    return export_mp3(mixed_file, output_file, bitrate)
