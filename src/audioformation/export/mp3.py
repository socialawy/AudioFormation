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