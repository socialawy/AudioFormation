
"""
QC Final — Validation of mixed audio before export (Pipeline Node 7).

Checks mixed files in 06_MIX/renders/ against broadcast standards:
- Integrated LUFS (target ± deviation)
- True Peak (<= limit)
- Clipping (0 tolerance)

If this gate fails, the user must adjust mix settings and re-run mix.
"""

import json
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
                messages=[f"Measurement error: {e}"]
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

        report.results.append(FinalMixResult(
            filename=f.name,
            duration_sec=duration,
            lufs=lufs,
            true_peak=tp,
            clipped=clipped,
            status=status,
            messages=messages
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
