#!/usr/bin/env python3
"""
AudioFormation project state aggregator.
Reads CODE artifacts, outputs docs/STATE.json.
Run after any milestone: python tools/docstate.py

Zero markdown parsing. Zero regex on prose.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

projects: List[Dict[str, Any]] = []

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "PROJECTS"
SRC = ROOT / "src" / "audioformation"


def get_version():
    toml = (ROOT / "pyproject.toml").read_text()
    for line in toml.splitlines():
        if line.strip().startswith("version"):
            return line.split("=")[1].strip().strip('"')
    return "unknown"


def get_dependencies():
    toml = (ROOT / "pyproject.toml").read_text()
    deps = []
    in_deps = False
    for line in toml.splitlines():
        if "dependencies" in line and "=" in line:
            in_deps = True
            continue
        if in_deps:
            if line.strip() == "]":
                break
            deps.append(line.strip().strip('",'))
    return deps


def get_test_count():
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "--co", "-q"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=30,
        )
        # Last line: "264 tests collected"
        for line in r.stdout.strip().splitlines()[::-1]:
            if "test" in line and "collected" in line:
                return int(line.split()[0])
    except Exception:
        pass
    return None


def get_engines():
    """Read registered engines from registry.py without importing."""
    registry = SRC / "engines" / "registry.py"
    if not registry.exists():
        return []
    text = registry.read_text()
    engines = []
    for line in text.splitlines():
        # Look for engine name strings in registration
        for name in ["edge", "gtts", "xtts", "elevenlabs", "openai"]:
            if f'"{name}"' in line or f"'{name}'" in line:
                if name not in engines:
                    engines.append(name)
    return engines


def get_source_files():
    """Count .py files in src/."""
    return len(list(SRC.rglob("*.py")))


def get_test_files():
    """Count test files."""
    return len(list((ROOT / "tests").rglob("test_*.py")))


def get_node_status():
    """Aggregate node status across all projects,
    or report built/planned from source."""
    nodes = [
        "bootstrap",
        "ingest",
        "validate",
        "generate",
        "qc_scan",
        "process",
        "compose",
        "mix",
        "qc_final",
        "export",
    ]
    status = {}
    for node in nodes:
        # Check if the node has real implementation
        # by looking for its handler in cli.py or pipeline.py
        cli_text = (SRC / "cli.py").read_text()
        if f"def {node}" in cli_text or f"'{node}'" in cli_text:
            status[node] = "built"
        else:
            status[node] = "planned"
    return status


def get_git_info():
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout.strip()

        log = (
            subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            .stdout.strip()
            .splitlines()
        )

        clean = (
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=ROOT,
            ).stdout.strip()
            == ""
        )

        return {"branch": branch, "clean": clean, "recent_commits": log}
    except Exception:
        return {"branch": "unknown", "clean": False, "recent_commits": []}


def get_projects():
    """List projects and their pipeline status."""
    projects = []
    if not PROJECTS_DIR.exists():
        return projects
    for p in sorted(PROJECTS_DIR.iterdir()):
        if not p.is_dir():
            continue
        status_file = p / "pipeline-status.json"
        if status_file.exists():
            data = json.loads(status_file.read_text())
            nodes = data.get("nodes", {})
            projects.append(
                {
                    "id": p.name,
                    "nodes": {k: v.get("status", "unknown") for k, v in nodes.items()},
                }
            )
        else:
            projects.append({"id": p.name, "nodes": {}})
    return projects


def main():
    state = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": get_version(),
        "test_count": get_test_count(),
        "source_files": get_source_files(),
        "test_files": get_test_files(),
        "engines_registered": get_engines(),
        "pipeline_nodes": get_node_status(),
        "dependencies": get_dependencies(),
        "git": get_git_info(),
        "projects": get_projects(),
    }

    out = ROOT / "docs" / "STATE.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"✅ State written to {out}")
    print(f"   Version: {state['version']}")
    print(f"   Tests: {state['test_count']}")
    print(f"   Engines: {state['engines_registered']}")
    print(f"   Source files: {state['source_files']}")


if __name__ == "__main__":
    main()
