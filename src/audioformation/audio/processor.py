"""
Audio processing — LUFS measurement, normalization, silence trimming,
crossfade stitching.

Uses pyloudnorm for in-process LUFS metering.
Uses ffmpeg loudnorm filter for batch normalization.
Uses pydub for audio manipulation (trim, crossfade, convert).
"""

import subprocess
import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


# ──────────────────────────────────────────────
# LUFS Measurement
# ──────────────────────────────────────────────


def measure_lufs(audio_path: Path) -> float:
    """
    Measure integrated LUFS of an audio file.

    Uses pyloudnorm for in-process analysis.
    Returns LUFS value (typically -10 to -30).
    """
    import pyloudnorm as pyln

    data, rate = sf.read(str(audio_path))

    # Ensure 2D array (mono → single column)
    if data.ndim == 1:
        data = data.reshape(-1, 1)

    meter = pyln.Meter(rate)
    loudness = meter.integrated_loudness(data)

    return float(loudness)


def measure_true_peak(audio_path: Path) -> float:
    """
    Measure true peak level in dBTP.

    Uses numpy for peak detection on the audio samples.
    """
    data, rate = sf.read(str(audio_path))

    if data.ndim > 1:
        peak = np.max(np.abs(data))
    else:
        peak = np.max(np.abs(data))

    if peak == 0:
        return -120.0  # Silence

    db = 20 * np.log10(peak)
    return float(db)


def detect_clipping(audio_path: Path, threshold_dbfs: float = -0.5) -> dict[str, Any]:
    """
    Detect clipping in an audio file.

    Returns dict with:
    - clipped: bool
    - peak_dbfs: float
    - clipped_samples: int
    - total_samples: int
    """
    data, rate = sf.read(str(audio_path))

    if data.ndim > 1:
        data = data.flatten()

    threshold_linear = 10 ** (threshold_dbfs / 20)
    clipped_samples = int(np.sum(np.abs(data) > threshold_linear))
    peak = float(np.max(np.abs(data)))
    peak_dbfs = 20 * np.log10(peak) if peak > 0 else -120.0

    return {
        "clipped": clipped_samples > 0,
        "peak_dbfs": peak_dbfs,
        "clipped_samples": clipped_samples,
        "total_samples": len(data),
    }


# ──────────────────────────────────────────────
# Duration
# ──────────────────────────────────────────────


def get_duration(audio_path: Path) -> float:
    """Get audio duration in seconds."""
    info = sf.info(str(audio_path))
    return float(info.duration)


def get_sample_rate(audio_path: Path) -> int:
    """Get sample rate of audio file."""
    info = sf.info(str(audio_path))
    return info.samplerate


# ──────────────────────────────────────────────
# Normalization (ffmpeg loudnorm)
# ──────────────────────────────────────────────


def normalize_lufs(
    input_path: Path,
    output_path: Path,
    target_lufs: float = -16.0,
    true_peak: float = -1.0,
) -> bool:
    """
    Normalize audio to target LUFS using ffmpeg's loudnorm filter.

    Two-pass approach for best results:
    1. Measure current loudness
    2. Apply normalization with measured values

    Returns True on success, False on failure.
    """
    # Pass 1: Measure
    measure_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        f"loudnorm=I={target_lufs}:TP={true_peak}:print_format=json",
        "-f",
        "null",
        "-",
    ]

    try:
        result = subprocess.run(
            measure_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    # Parse measured values from stderr (ffmpeg outputs to stderr)
    measured = _parse_loudnorm_stats(result.stderr)
    if not measured:
        return False

    # Pass 2: Apply normalization
    normalize_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-af",
        (
            f"loudnorm=I={target_lufs}:TP={true_peak}"
            f":measured_I={measured['input_i']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_thresh={measured['input_thresh']}"
            f":linear=true"
        ),
        str(output_path),
    ]

    try:
        result = subprocess.run(
            normalize_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _parse_loudnorm_stats(stderr: str) -> dict[str, str] | None:
    """Parse loudnorm JSON output from ffmpeg stderr."""
    # Find the JSON block in stderr
    try:
        # ffmpeg prints the JSON at the end of stderr
        json_start = stderr.rfind("{")
        json_end = stderr.rfind("}") + 1

        if json_start == -1 or json_end <= json_start:
            return None

        stats = json.loads(stderr[json_start:json_end])

        return {
            "input_i": stats.get("input_i", "-24.0"),
            "input_lra": stats.get("input_lra", "7.0"),
            "input_tp": stats.get("input_tp", "-2.0"),
            "input_thresh": stats.get("input_thresh", "-34.0"),
        }
    except (json.JSONDecodeError, KeyError):
        return None


# ──────────────────────────────────────────────
# Silence trimming
# ──────────────────────────────────────────────


def trim_silence(
    input_path: Path,
    output_path: Path,
    threshold_db: float = -40.0,
    min_silence_ms: int = 100,
) -> bool:
    """
    Trim leading and trailing silence from an audio file using ffmpeg.

    Args:
        threshold_db: Silence threshold in dB.
        min_silence_ms: Minimum silence duration to detect.

    Returns True on success.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-af",
        (
            f"silenceremove=start_periods=1:start_threshold={threshold_db}dB"
            f":start_duration={min_silence_ms / 1000},"
            f"areverse,"
            f"silenceremove=start_periods=1:start_threshold={threshold_db}dB"
            f":start_duration={min_silence_ms / 1000},"
            f"areverse"
        ),
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ──────────────────────────────────────────────
# Crossfade stitching
# ──────────────────────────────────────────────


def crossfade_stitch(
    audio_paths: list[Path],
    output_path: Path,
    crossfade_ms: int = 120,
    leading_silence_ms: int = 100,
) -> bool:
    """
    Stitch multiple audio files with crossfade overlap.

    Uses pydub for crossfade.

    Args:
        audio_paths: Ordered list of audio file paths.
        output_path: Where to write the stitched result.
        crossfade_ms: Overlap duration in milliseconds.
        leading_silence_ms: Silence to prepend.

    Returns True on success.
    """
    from pydub import AudioSegment

    if not audio_paths:
        return False

    try:
        # Start with leading silence
        if leading_silence_ms > 0:
            combined = AudioSegment.silent(duration=leading_silence_ms)
        else:
            combined = AudioSegment.empty()

        # Load first chunk
        first = AudioSegment.from_file(str(audio_paths[0]))
        combined += first

        # Append remaining with crossfade
        for path in audio_paths[1:]:
            chunk = AudioSegment.from_file(str(path))

            # Clamp crossfade to not exceed chunk lengths
            effective_fade = min(
                crossfade_ms,
                len(combined),
                len(chunk),
            )

            if effective_fade > 0:
                combined = combined.append(chunk, crossfade=effective_fade)
            else:
                combined += chunk

        # Export
        combined.export(str(output_path), format=_format_from_path(output_path))
        return True

    except Exception:
        return False


def _format_from_path(path: Path) -> str:
    """Infer pydub export format from file extension."""
    ext = path.suffix.lower()
    formats = {
        ".wav": "wav",
        ".mp3": "mp3",
        ".flac": "flac",
        ".ogg": "ogg",
        ".m4a": "ipod",
    }
    return formats.get(ext, "wav")


def batch_process_project(project_id: str) -> dict[str, Any]:
    """
    Batch process all generated audio files in a project.

    Applies normalization and silence trimming to all chunks.
    Returns processing statistics.
    """
    from audioformation.project import get_project_path

    project_path = get_project_path(project_id)
    gen_dir = project_path / "03_GENERATED"
    processed_dir = project_path / "03_GENERATED" / "processed"
    processed_dir.mkdir(exist_ok=True)

    stats = {"total_files": 0, "processed": 0, "failed": 0, "errors": []}

    # Find all audio chunks
    audio_files = list(gen_dir.glob("*.wav"))
    stats["total_files"] = len(audio_files)

    for audio_file in audio_files:
        try:
            # Skip if already processed
            processed_file = processed_dir / audio_file.name
            if processed_file.exists():
                stats["processed"] += 1
                continue

            # Apply normalization
            temp_file = processed_file.with_suffix(".temp.wav")
            if normalize_lufs(audio_file, temp_file):
                # Apply silence trimming
                if trim_silence(temp_file, processed_file):
                    stats["processed"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"].append(
                        f"Silence trimming failed: {audio_file.name}"
                    )

                # Clean up temp file
                temp_file.unlink(missing_ok=True)
            else:
                stats["failed"] += 1
                stats["errors"].append(f"Normalization failed: {audio_file.name}")

        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"Processing error {audio_file.name}: {str(e)}")

    return stats
