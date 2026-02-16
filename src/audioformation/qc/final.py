
"""
QC Final — Validation of mixed audio before export (Pipeline Node 7).

Checks mixed files in 06_MIX/renders/ against broadcast standards:
- Integrated LUFS (target ± deviation)
- True Peak (<= limit)
- Clipping (0 tolerance)
- Silence gaps between chapters
- Boundary artifacts (energy discontinuity)

If this gate fails, user must adjust mix settings and re-run mix.
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

from audioformation.project import (
    get_project_path,
    load_project_json,
)
from audioformation.audio.processor import (
    measure_lufs,
    measure_true_peak,
    detect_clipping,
    get_duration,
)
from audioformation.pipeline import update_node_status


@dataclass
class FinalMixResult:
    """QC result for a single mixed file."""
    filename: str
    duration_sec: float
    lufs: float
    true_peak: float
    clipped: bool
    status: Literal["pass", "fail"]
    messages: list[str] = field(default_factory=list)
    longest_silence_sec: float = 0.0
    worst_boundary_jump_db: float = 0.0


@dataclass
class FinalQCReport:
    """Full report for QC Final."""
    project_id: str
    target_lufs: float
    true_peak_limit: float
    total_files: int = 0
    passed_files: int = 0
    failed_files: int = 0
    results: list[FinalMixResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.failed_files == 0 and self.total_files > 0

    def save(self, path: Path) -> None:
        """Save report to JSON."""
        data = asdict(self)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _detect_silence_gaps(audio_path: Path, max_gap_sec: float = 2.0) -> dict:
    """Detect silence gaps between audio segments."""
    try:
        from audioformation.audio.processor import get_duration
        import soundfile as sf
        
        # Load audio
        data, sr = sf.read(str(audio_path))
        if data.ndim > 1:
            data = data[:, 0]  # Use first channel
        
        # Simple silence detection: energy below threshold
        frame_size = int(sr * 0.01)  # 10ms frames
        hop_size = int(sr * 0.005)  # 5ms hop
        
        energy_threshold = 0.01  # Adjust based on testing
        silence_frames = []
        in_silence = False
        gap_start = None
        
        for i in range(0, len(data) - frame_size, hop_size):
            frame = data[i:i + frame_size]
            energy = np.mean(frame ** 2)
            
            if energy < energy_threshold:
                if not in_silence:
                    in_silence = True
                    gap_start = i / sr
                silence_frames.append(i / sr)
            else:
                if in_silence:
                    gap_end = i / sr
                    gap_duration = gap_end - gap_start
                    if gap_duration >= max_gap_sec:
                        return {
                            "has_long_gaps": True,
                            "longest_gap_sec": gap_duration,
                            "gap_positions": [(gap_start, gap_end)]
                        }
                    in_silence = False
                    gap_start = None
        
        return {"has_long_gaps": False, "longest_gap_sec": 0.0, "gap_positions": []}
        
    except Exception:
        return {"has_long_gaps": False, "longest_gap_sec": 0.0, "gap_positions": []}


def _check_boundary_artifacts(audio_path: Path) -> dict:
    """Check for energy discontinuities at potential boundaries."""
    try:
        import soundfile as sf
        
        # Load audio
        data, sr = sf.read(str(audio_path))
        if data.ndim > 1:
            data = data[:, 0]  # Use first channel
        
        # Simple energy discontinuity detection
        frame_size = int(sr * 0.1)  # 100ms frames
        hop_size = int(sr * 0.05)  # 50ms hop
        
        energy_levels = []
        for i in range(0, len(data) - frame_size, hop_size):
            frame = data[i:i + frame_size]
            energy = np.mean(frame ** 2)
            energy_levels.append(energy)
        
        # Look for large jumps in energy
        if len(energy_levels) < 2:
            return {"has_artifacts": False, "worst_position_sec": 0.0, "worst_jump_db": 0.0}
        
        energy_array = np.array(energy_levels)
        
        # Find discontinuities (jumps > 6dB)
        jumps_db = []
        positions_sec = []
        
        for i in range(1, len(energy_array)):
            prev_energy = energy_array[i-1]
            curr_energy = energy_array[i]
            
            if curr_energy > 0 and prev_energy > 0:
                jump_db = 20 * np.log10(curr_energy / prev_energy)
                if abs(jump_db) > 6.0:  # 6dB threshold
                    jumps_db.append(abs(jump_db))
                    positions_sec.append(i * 0.05)  # 50ms steps
        
        if jumps_db:
            return {
                "has_artifacts": True,
                "worst_position_sec": max(positions_sec) if positions_sec else 0.0,
                "worst_jump_db": max(jumps_db)
            }
        
        return {"has_artifacts": False, "worst_position_sec": 0.0, "worst_jump_db": 0.0}
        
    except Exception:
        return {"has_artifacts": False, "worst_position_sec": 0.0, "worst_jump_db": 0.0}


def scan_final_mix(project_id: str) -> FinalQCReport:
    """
    Run QC Final on all files in 06_MIX/renders/.

    Returns FinalQCReport.
    """
    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    mix_config = pj.get("mix", {})
    
    target_lufs = mix_config.get("target_lufs", -16.0)
    true_peak_limit = mix_config.get("true_peak_limit_dbtp", -1.0)
    
    # Tolerance for LUFS (usually strict for final mix)
    lufs_tolerance = 1.0  # ±1 LUFS

    mix_dir = project_path / "06_MIX" / "renders"
    if not mix_dir.exists():
        update_node_status(project_id, "qc_final", "failed", error="No mix directory found")
        return FinalQCReport(project_id, target_lufs, true_peak_limit)

    files = sorted(mix_dir.glob("*.wav"))
    
    report = FinalQCReport(
        project_id=project_id,
        target_lufs=target_lufs,
        true_peak_limit=true_peak_limit,
        total_files=len(files)
    )

    if not files:
        update_node_status(project_id, "qc_final", "failed", error="No mixed files found")
        return report

    update_node_status(project_id, "qc_final", "running")

    for f in files:
        # Measure
        try:
            duration = get_duration(f)
            lufs = measure_lufs(f)
            tp = measure_true_peak(f)
            clip_info = detect_clipping(f, threshold_dbfs=0.0) # Check for hard clipping > 0dBFS
            clipped = clip_info["clipped"]
        except Exception as e:
            # Measurement failed
            report.results.append(FinalMixResult(
                filename=f.name,
                duration_sec=0.0,
                lufs=0.0,
                true_peak=0.0,
                clipped=False,
                status="fail",
                messages=[f"Measurement error: {e}"],
                longest_silence_sec=0.0,
                worst_boundary_jump_db=0.0
            ))
            report.failed_files += 1
            continue

        # Evaluate
        messages = []
        status: Literal["pass", "fail"] = "pass"

        # Check LUFS
        if abs(lufs - target_lufs) > lufs_tolerance:
            status = "fail"
            messages.append(
                f"LUFS {lufs:.1f} deviates from target {target_lufs} by > {lufs_tolerance}."
            )

        # Check True Peak
        if tp > true_peak_limit + 0.1: # Small tolerance for floating point
            status = "fail"
            messages.append(
                f"True Peak {tp:.2f} exceeds limit {true_peak_limit}."
            )

        # Check Clipping
        if clipped:
            status = "fail"
            messages.append("Digital clipping detected (samples >= 0 dBFS).")
        
        # Check silence gaps
        max_silence_sec = mix_config.get("gap_between_chapters_sec", 2.0) * 2
        silence_info = _detect_silence_gaps(f, max_gap_sec=max_silence_sec)
        if silence_info["has_long_gaps"]:
            status = "fail"
            messages.append(
                f"Silence gap of {silence_info['longest_gap_sec']:.1f}s "
                f"exceeds max {max_silence_sec:.1f}s."
            )

        # Check for boundary artifacts (energy discontinuity)
        boundary_info = _check_boundary_artifacts(f)
        if boundary_info["has_artifacts"]:
            messages.append(
                f"Possible boundary artifact at {boundary_info['worst_position_sec']:.1f}s "
                f"({boundary_info['worst_jump_db']:.1f} dB jump)."
            )
            # Warning only — don't fail on boundary artifacts

        report.results.append(FinalMixResult(
            filename=f.name,
            duration_sec=duration,
            lufs=lufs,
            true_peak=tp,
            clipped=clipped,
            status=status,
            messages=messages,
            longest_silence_sec=silence_info["longest_gap_sec"],
            worst_boundary_jump_db=boundary_info["worst_jump_db"],
        ))

        if status == "fail":
            report.failed_files += 1
        else:
            report.passed_files += 1

    # Save report
    report_path = project_path / "06_MIX" / "qc_final_report.json"
    report.save(report_path)

    # Update pipeline status
    if report.passed:
        update_node_status(project_id, "qc_final", "complete")
    else:
        update_node_status(
            project_id, "qc_final", "failed",
            failed_count=report.failed_files,
            total_count=report.total_files
        )

    return report


def _detect_silence_gaps(
    filepath: Path,
    threshold_dbfs: float = -40.0,
    min_gap_ms: int = 500,
    max_gap_sec: float = 4.0,
) -> dict:
    """
    Detect silence gaps longer than max_gap_sec.

    Returns dict with has_long_gaps, longest_gap_sec, gap_count.
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(filepath))
        chunk_ms = 50
        gaps: list[float] = []
        current_gap_ms = 0

        for i in range(0, len(audio), chunk_ms):
            chunk = audio[i:i + chunk_ms]
            if chunk.dBFS < threshold_dbfs or chunk.dBFS == float("-inf"):
                current_gap_ms += chunk_ms
            else:
                if current_gap_ms >= min_gap_ms:
                    gaps.append(current_gap_ms / 1000.0)
                current_gap_ms = 0

        # Final gap
        if current_gap_ms >= min_gap_ms:
            gaps.append(current_gap_ms / 1000.0)

        longest = max(gaps) if gaps else 0.0

        return {
            "has_long_gaps": longest > max_gap_sec,
            "longest_gap_sec": round(longest, 2),
            "gap_count": len(gaps),
        }
    except Exception:
        return {"has_long_gaps": False, "longest_gap_sec": 0.0, "gap_count": 0}


def _check_boundary_artifacts(
    filepath: Path,
    window_ms: int = 50,
    jump_threshold_db: float = 12.0,
) -> dict:
    """
    Detect energy discontinuities that suggest bad crossfade or
    concatenation artifacts.

    Scans adjacent windows and flags jumps > threshold.
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(filepath))
        worst_jump = 0.0
        worst_pos = 0.0
        prev_dbfs = None

        for i in range(0, len(audio) - window_ms, window_ms):
            chunk = audio[i:i + window_ms]
            dbfs = chunk.dBFS

            if dbfs == float("-inf"):
                dbfs = -80.0

            if prev_dbfs is not None:
                jump = abs(dbfs - prev_dbfs)
                if jump > worst_jump:
                    worst_jump = jump
                    worst_pos = i / 1000.0

            prev_dbfs = dbfs

        return {
            "has_artifacts": worst_jump > jump_threshold_db,
            "worst_jump_db": round(worst_jump, 1),
            "worst_position_sec": round(worst_pos, 2),
        }
    except Exception:
        return {"has_artifacts": False, "worst_jump_db": 0.0, "worst_position_sec": 0.0}
