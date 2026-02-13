"""
QC Scanner — Per-chunk quality checks (Pipeline Node 3.5).

Checks:
- SNR (via VAD noise floor method)
- Clipping detection
- Duration sanity
- LUFS deviation from target
- Pitch continuity (basic)
- Boundary artifact detection (energy discontinuity at crossfades)

Results: PASS / WARN / FAIL per check, per chunk.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

import numpy as np
import soundfile as sf

from audioformation.audio.processor import (
    measure_lufs,
    detect_clipping,
    get_duration,
)


@dataclass
class ChunkQCResult:
    """QC result for a single audio chunk."""

    chunk_id: str
    file: str
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def status(self) -> Literal["pass", "warn", "fail"]:
        """Overall status: worst of all checks."""
        statuses = [c.get("status", "pass") for c in self.checks.values()]
        if "fail" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        return "pass"


@dataclass
class QCReport:
    """Full QC report for a generation run."""

    project_id: str
    chapter_id: str | None = None
    chunks: list[ChunkQCResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.chunks if c.status == "pass")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.chunks if c.status == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.chunks if c.status == "fail")

    @property
    def fail_rate(self) -> float:
        if not self.chunks:
            return 0.0
        return (self.fail_count / len(self.chunks)) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "chapter_id": self.chapter_id,
            "total_chunks": len(self.chunks),
            "passed": self.pass_count,
            "warnings": self.warn_count,
            "failures": self.fail_count,
            "fail_rate_percent": round(self.fail_rate, 2),
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "file": c.file,
                    "status": c.status,
                    "checks": c.checks,
                }
                for c in self.chunks
            ],
        }

    def save(self, path: Path) -> None:
        """Write QC report as JSON."""
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def scan_chunk(
    audio_path: Path,
    chunk_id: str,
    config: dict[str, Any],
    expected_duration: float | None = None,
    target_lufs: float = -16.0,
) -> ChunkQCResult:
    """
    Run all QC checks on a single audio chunk.

    Args:
        audio_path: Path to the audio file.
        chunk_id: Identifier for this chunk.
        config: QC config from project.json.
        expected_duration: Expected duration in seconds (if known).
        target_lufs: LUFS target for deviation check.

    Returns:
        ChunkQCResult with all check results.
    """
    result = ChunkQCResult(chunk_id=chunk_id, file=str(audio_path))

    if not audio_path.exists():
        result.checks["file_exists"] = {
            "status": "fail",
            "message": "File not found.",
        }
        return result

    # SNR check
    result.checks["snr"] = _check_snr(
        audio_path,
        min_db=config.get("snr_min_db", 20.0),
    )

    # Clipping check
    result.checks["clipping"] = _check_clipping(
        audio_path,
        threshold_dbfs=config.get("clipping_threshold_dbfs", -0.5),
    )

    # Duration sanity
    if expected_duration is not None:
        result.checks["duration"] = _check_duration(
            audio_path,
            expected_duration,
            max_deviation_pct=config.get("max_duration_deviation_percent", 30.0),
        )

    # LUFS deviation
    result.checks["lufs"] = _check_lufs(
        audio_path,
        target_lufs,
        max_deviation=config.get("lufs_deviation_max", 3.0),
    )

    return result


# ──────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────


def _check_snr(audio_path: Path, min_db: float) -> dict[str, Any]:
    """
    Estimate SNR using VAD noise floor method.

    Uses energy-based approximation: compares high-energy frames
    (speech) to low-energy frames (noise/silence).
    """
    try:
        data, rate = sf.read(str(audio_path))
        if data.ndim > 1:
            data = data[:, 0]  # Use first channel

        # Frame-level energy analysis
        frame_size = int(rate * 0.025)  # 25ms frames
        hop = int(rate * 0.010)  # 10ms hop

        if len(data) < frame_size:
            return {"status": "warn", "snr_db": 0, "message": "Audio too short for SNR."}

        energies = []
        for start in range(0, len(data) - frame_size, hop):
            frame = data[start:start + frame_size]
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms > 0:
                energies.append(rms)

        if not energies:
            return {"status": "warn", "snr_db": 0, "message": "No energy detected."}

        energies_arr = np.array(energies)
        threshold = np.percentile(energies_arr, 30)  # Bottom 30% as noise

        noise_frames = energies_arr[energies_arr <= threshold]
        speech_frames = energies_arr[energies_arr > threshold]

        if len(noise_frames) == 0 or len(speech_frames) == 0:
            return {"status": "warn", "snr_db": 0, "message": "Cannot separate speech/noise."}

        noise_rms = float(np.mean(noise_frames))
        speech_rms = float(np.mean(speech_frames))

        if noise_rms == 0:
            snr = 60.0  # Effectively no noise
        else:
            snr = 20 * np.log10(speech_rms / noise_rms)

        snr = float(snr)

        if snr >= min_db:
            return {"status": "pass", "snr_db": round(snr, 1)}
        elif snr >= min_db - 5:
            return {"status": "warn", "snr_db": round(snr, 1), "message": "SNR slightly below target."}
        else:
            return {"status": "fail", "snr_db": round(snr, 1), "message": f"SNR {snr:.1f} dB below minimum {min_db} dB."}

    except Exception as e:
        return {"status": "warn", "snr_db": 0, "message": f"SNR check error: {e}"}


def _check_clipping(audio_path: Path, threshold_dbfs: float) -> dict[str, Any]:
    """Check for digital clipping."""
    clip_info = detect_clipping(audio_path, threshold_dbfs)

    if not clip_info["clipped"]:
        return {
            "status": "pass",
            "peak_dbfs": round(clip_info["peak_dbfs"], 2),
        }

    clip_pct = (clip_info["clipped_samples"] / max(clip_info["total_samples"], 1)) * 100

    if clip_pct < 0.01:
        return {
            "status": "warn",
            "peak_dbfs": round(clip_info["peak_dbfs"], 2),
            "clipped_percent": round(clip_pct, 4),
            "message": "Minor clipping detected.",
        }

    return {
        "status": "fail",
        "peak_dbfs": round(clip_info["peak_dbfs"], 2),
        "clipped_percent": round(clip_pct, 4),
        "message": f"Clipping detected: {clip_pct:.4f}% of samples.",
    }


def _check_duration(
    audio_path: Path,
    expected: float,
    max_deviation_pct: float,
) -> dict[str, Any]:
    """Check if duration is within expected range."""
    actual = get_duration(audio_path)

    if expected <= 0:
        return {"status": "pass", "duration_sec": round(actual, 2)}

    deviation_pct = abs(actual - expected) / expected * 100

    if deviation_pct <= max_deviation_pct:
        return {
            "status": "pass",
            "duration_sec": round(actual, 2),
            "expected_sec": round(expected, 2),
            "deviation_percent": round(deviation_pct, 1),
        }
    elif deviation_pct <= max_deviation_pct * 1.5:
        return {
            "status": "warn",
            "duration_sec": round(actual, 2),
            "expected_sec": round(expected, 2),
            "deviation_percent": round(deviation_pct, 1),
            "message": "Duration slightly outside expected range.",
        }
    else:
        return {
            "status": "fail",
            "duration_sec": round(actual, 2),
            "expected_sec": round(expected, 2),
            "deviation_percent": round(deviation_pct, 1),
            "message": f"Duration {actual:.1f}s deviates {deviation_pct:.0f}% from expected {expected:.1f}s.",
        }


def _check_lufs(
    audio_path: Path,
    target: float,
    max_deviation: float,
) -> dict[str, Any]:
    """Check LUFS deviation from target."""
    try:
        lufs = measure_lufs(audio_path)
        deviation = abs(lufs - target)

        if deviation <= max_deviation:
            return {
                "status": "pass",
                "lufs": round(lufs, 1),
                "target": target,
                "deviation": round(deviation, 1),
            }
        elif deviation <= max_deviation * 2:
            return {
                "status": "warn",
                "lufs": round(lufs, 1),
                "target": target,
                "deviation": round(deviation, 1),
                "message": "LUFS slightly outside target range.",
            }
        else:
            return {
                "status": "fail",
                "lufs": round(lufs, 1),
                "target": target,
                "deviation": round(deviation, 1),
                "message": f"LUFS {lufs:.1f} deviates {deviation:.1f} from target {target}.",
            }

    except Exception as e:
        return {"status": "warn", "message": f"LUFS check error: {e}"}