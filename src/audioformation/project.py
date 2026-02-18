"""
Project CRUD — create, list, load, validate structure.

Every project is a directory under PROJECTS_ROOT containing:
- project.json (single source of truth)
- pipeline-status.json (execution state)
- Folder structure (00_CONFIG through 07_EXPORT)
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audioformation.config import (
    PROJECTS_ROOT,
    PROJECT_DIRS,
    PIPELINE_NODES,
    DEFAULT_CHUNK_MAX_CHARS,
    DEFAULT_CROSSFADE_MS,
    DEFAULT_CROSSFADE_MIN_MS,
    DEFAULT_LEADING_SILENCE_MS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_FAIL_THRESHOLD_PCT,
    DEFAULT_EDGE_RATE_LIMIT_MS,
    DEFAULT_EDGE_CONCURRENCY,
    DEFAULT_XTTS_TEMPERATURE,
    DEFAULT_XTTS_REPETITION_PENALTY,
    DEFAULT_SNR_MIN_DB,
    DEFAULT_MAX_DURATION_DEVIATION_PCT,
    DEFAULT_CLIPPING_THRESHOLD_DBFS,
    DEFAULT_LUFS_DEVIATION_MAX,
    DEFAULT_PITCH_JUMP_MAX_ST,
    DEFAULT_TARGET_LUFS,
    DEFAULT_TRUE_PEAK_LIMIT,
    DEFAULT_CHAPTER_GAP_SEC,
    DEFAULT_VAD_THRESHOLD,
    DEFAULT_VAD_THRESHOLD_AR,
    DEFAULT_DUCK_LOOK_AHEAD_MS,
    DEFAULT_DUCK_ATTACK_MS,
    DEFAULT_DUCK_RELEASE_MS,
    DEFAULT_DUCK_ATTENUATION_DB,
    DEFAULT_MP3_BITRATE,
    DEFAULT_M4B_AAC_BITRATE,
)
from audioformation.utils.security import sanitize_project_id


def get_project_path(project_id: str) -> Path:
    """Resolve and validate a project directory path."""
    # CODEQL FIX: Explicit Input Validation
    # 1. Enforce strict character set (Alphanumeric, underscore, hyphen)
    if not re.fullmatch(r"^[A-Za-z0-9_-]+$", project_id):
        raise ValueError(f"Security Alert: Invalid Project ID format: {project_id}")

    # 2. Construct path safely using joinpath (avoid string concatenation)
    path = PROJECTS_ROOT.joinpath(project_id)

    # 3. Resolve to absolute path to handle '..'
    try:
        resolved_path = path.resolve()
        resolved_root = PROJECTS_ROOT.resolve()
    except OSError as e:
        raise ValueError(f"Invalid path resolution: {e}")

    # 4. Strict Containment Check (Allowlist)
    # Ensure the resolved path starts with the resolved root
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"Security Alert: Path traversal detected: {project_id}")

    return path


def create_project(project_id: str) -> Path:
    """
    Create a new project with full directory structure,
    default project.json, and initial pipeline-status.json.

    Returns the project directory path.
    Raises FileExistsError if project already exists.
    """
    # FIX: Explicitly sanitize input here so get_project_path receives a valid ID
    safe_id = sanitize_project_id(project_id)
    
    project_path = get_project_path(safe_id)

    if project_path.exists():
        raise FileExistsError(f"Project already exists: {safe_id}")

    # Create all directories
    for dir_rel in PROJECT_DIRS:
        (project_path / dir_rel).mkdir(parents=True, exist_ok=True)
        # Add .gitkeep to keep empty dirs in version control
        gitkeep = project_path / dir_rel / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    # Write default project.json
    project_json = _default_project_json(safe_id)
    _write_json(project_path / "project.json", project_json)

    # Write initial pipeline-status.json
    pipeline_status = _initial_pipeline_status(safe_id)
    _write_json(project_path / "pipeline-status.json", pipeline_status)

    # Write .gitignore
    _write_gitignore(project_path)

    return project_path


def list_projects() -> list[dict[str, Any]]:
    """
    List all projects under PROJECTS_ROOT.

    Returns list of dicts with id, created, and pipeline status summary.
    """
    if not PROJECTS_ROOT.exists():
        return []

    projects = []
    for entry in sorted(PROJECTS_ROOT.iterdir()):
        if entry.is_dir() and (entry / "project.json").exists():
            try:
                pj = load_project_json(entry.name)
                ps = load_pipeline_status(entry.name)
                projects.append(
                    {
                        "id": pj.get("id", entry.name),
                        "created": pj.get("created", "unknown"),
                        "languages": pj.get("languages", []),
                        "chapters": len(pj.get("chapters", [])),
                        "pipeline_node": _current_node(ps),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                projects.append(
                    {
                        "id": entry.name,
                        "created": "unknown",
                        "languages": [],
                        "chapters": 0,
                        "pipeline_node": "error",
                    }
                )

    return projects


def load_project_json(project_id: str) -> dict[str, Any]:
    """Load and return project.json for the given project."""
    path = get_project_path(project_id) / "project.json"
    if not path.exists():
        raise FileNotFoundError(f"project.json not found for '{project_id}'")
    return json.loads(path.read_text(encoding="utf-8"))


def save_project_json(project_id: str, data: dict[str, Any]) -> None:
    """Write project.json for the given project."""
    path = get_project_path(project_id) / "project.json"
    _write_json(path, data)


def load_pipeline_status(project_id: str) -> dict[str, Any]:
    """Load and return pipeline-status.json for the given project."""
    path = get_project_path(project_id) / "pipeline-status.json"
    if not path.exists():
        raise FileNotFoundError(f"pipeline-status.json not found for '{project_id}'")
    return json.loads(path.read_text(encoding="utf-8"))


def save_pipeline_status(project_id: str, data: dict[str, Any]) -> None:
    """Write pipeline-status.json for the given project."""
    path = get_project_path(project_id) / "pipeline-status.json"
    _write_json(path, data)


def project_exists(project_id: str) -> bool:
    """Check if a project directory and project.json exist."""
    try:
        path = get_project_path(project_id)
        return (path / "project.json").exists()
    except ValueError:
        return False


# ──────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON with consistent formatting."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _current_node(status: dict[str, Any]) -> str:
    """Determine the current pipeline node from status."""
    nodes = status.get("nodes", {})
    for node in reversed(PIPELINE_NODES):
        node_status = nodes.get(node, {}).get("status", "pending")
        if node_status in ("complete", "partial"):
            return node
    return "new"


def _default_project_json(project_id: str) -> dict[str, Any]:
    """Generate the default project.json skeleton."""
    return {
        "id": project_id,
        "version": "1.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "languages": ["ar", "en"],
        "chapters": [],
        "characters": {
            "narrator": {
                "name": "Narrator",
                "engine": "edge",
                "voice": "ar-SA-HamedNeural",
                "dialect": "msa",
                "persona": "Default narrator",
                "reference_audio": None,
            }
        },
        "generation": {
            "chunk_max_chars": DEFAULT_CHUNK_MAX_CHARS,
            "chunk_strategy": "breath_group",
            "crossfade_ms": DEFAULT_CROSSFADE_MS,
            "crossfade_min_ms": DEFAULT_CROSSFADE_MIN_MS,
            "leading_silence_ms": DEFAULT_LEADING_SILENCE_MS,
            "max_retries_per_chunk": DEFAULT_MAX_RETRIES,
            "fail_threshold_percent": DEFAULT_FAIL_THRESHOLD_PCT,
            "xtts_temperature": DEFAULT_XTTS_TEMPERATURE,
            "xtts_repetition_penalty": DEFAULT_XTTS_REPETITION_PENALTY,
            "edge_tts_rate_limit_ms": DEFAULT_EDGE_RATE_LIMIT_MS,
            "edge_tts_concurrency": DEFAULT_EDGE_CONCURRENCY,
            "edge_tts_ssml": True,
            "xtts_vram_management": "empty_cache_per_chapter",
        },
        "qc": {
            "snr_method": "vad_noise_floor",
            "snr_min_db": DEFAULT_SNR_MIN_DB,
            "max_duration_deviation_percent": DEFAULT_MAX_DURATION_DEVIATION_PCT,
            "clipping_threshold_dbfs": DEFAULT_CLIPPING_THRESHOLD_DBFS,
            "lufs_deviation_max": DEFAULT_LUFS_DEVIATION_MAX,
            "pitch_jump_max_semitones": DEFAULT_PITCH_JUMP_MAX_ST,
            "boundary_artifact_check": True,
        },
        "mix": {
            "master_volume": 0.9,
            "target_lufs": DEFAULT_TARGET_LUFS,
            "true_peak_limit_dbtp": DEFAULT_TRUE_PEAK_LIMIT,
            "gap_between_chapters_sec": DEFAULT_CHAPTER_GAP_SEC,
            "ducking": {
                "method": "vad",
                "vad_model": "silero-vad",
                "vad_threshold": DEFAULT_VAD_THRESHOLD,
                "vad_threshold_ar": DEFAULT_VAD_THRESHOLD_AR,
                "look_ahead_ms": DEFAULT_DUCK_LOOK_AHEAD_MS,
                "attack_ms": DEFAULT_DUCK_ATTACK_MS,
                "release_ms": DEFAULT_DUCK_RELEASE_MS,
                "attenuation_db": DEFAULT_DUCK_ATTENUATION_DB,
                "frequency_aware": False,
            },
        },
        "export": {
            "formats": ["mp3", "m4b"],
            "mp3_bitrate": DEFAULT_MP3_BITRATE,
            "m4b_aac_bitrate": DEFAULT_M4B_AAC_BITRATE,
            "include_cover_art": True,
            "cover_art": "00_CONFIG/cover.jpg",
            "chapter_transition": "silence",
            "chapter_transition_file": None,
            "metadata": {
                "author": "",
                "narrator": "",
                "publisher": "",
                "year": datetime.now(timezone.utc).year,
                "description": "",
            },
        },
    }


def _initial_pipeline_status(project_id: str) -> dict[str, Any]:
    """Generate initial pipeline-status.json with all nodes pending."""
    nodes = {}
    for node in PIPELINE_NODES:
        nodes[node] = {"status": "pending"}

    return {
        "project_id": project_id,
        "nodes": nodes,
    }


def _write_gitignore(project_path: Path) -> None:
    """Write the auto-generated .gitignore for a project."""
    content = """\
# AudioFormation — Auto-generated .gitignore

# API keys — NEVER commit
00_CONFIG/engines.json

# Generated audio (large files)
03_GENERATED/**/*.wav
03_GENERATED/**/*.mp3
04_SFX/procedural/**/*.wav
05_MUSIC/generated/**/*.wav
06_MIX/renders/**/*.wav

# Exports
07_EXPORT/**/*.mp3
07_EXPORT/**/*.m4b
07_EXPORT/**/*.wav
07_EXPORT/**/*.flac

# Keep directory structure
!**/.gitkeep
"""
    (project_path / ".gitignore").write_text(content, encoding="utf-8")
