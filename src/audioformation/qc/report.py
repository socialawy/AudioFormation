"""
QC report generation and display utilities.

Formats QC reports for CLI output and JSON export.
"""

from pathlib import Path

from audioformation.qc.scanner import QCReport


def format_report_summary(report: QCReport) -> str:
    """Format a QC report as a human-readable summary string."""
    lines = [
        f"QC Report: {report.project_id}",
        f"  Chapter: {report.chapter_id or 'all'}",
        f"  Chunks:  {len(report.chunks)}",
        f"  Passed:  {report.pass_count}",
        f"  Warns:   {report.warn_count}",
        f"  Failed:  {report.fail_count}",
        f"  Fail %:  {report.fail_rate:.1f}%",
        "",
    ]

    # List failures and warnings
    for chunk in report.chunks:
        if chunk.status == "fail":
            lines.append(f"  ✗ {chunk.chunk_id}: FAIL")
            for check_name, check_data in chunk.checks.items():
                if check_data.get("status") == "fail":
                    msg = check_data.get("message", "")
                    lines.append(f"    └─ {check_name}: {msg}")

        elif chunk.status == "warn":
            lines.append(f"  ⚠ {chunk.chunk_id}: WARN")
            for check_name, check_data in chunk.checks.items():
                if check_data.get("status") == "warn":
                    msg = check_data.get("message", "")
                    lines.append(f"    └─ {check_name}: {msg}")

    return "\n".join(lines)


def save_report(report: QCReport, output_dir: Path) -> Path:
    """
    Save QC report to the project's generated directory.

    Returns the path to the saved report.
    """
    if report.chapter_id:
        filename = f"qc_report_{report.chapter_id}.json"
    else:
        filename = "qc_report.json"

    output_path = output_dir / filename
    report.save(output_path)
    return output_path
