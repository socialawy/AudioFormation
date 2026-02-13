"""Shared test fixtures for AudioFormation."""

import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_projects(tmp_path, monkeypatch):
    """
    Autouse: redirect PROJECTS_ROOT to tmp_path/PROJECTS for every test.
    Prevents tests from touching real project data.
    """
    projects_root = tmp_path / "PROJECTS"
    projects_root.mkdir(exist_ok=True)

    # Patch everywhere PROJECTS_ROOT is imported
    targets = [
        "audioformation.config.PROJECTS_ROOT",
        "audioformation.project.PROJECTS_ROOT",
        "audioformation.pipeline.PROJECTS_ROOT",
        "audioformation.validation.PROJECTS_ROOT",
        "audioformation.ingest.PROJECTS_ROOT",
        "audioformation.generate.PROJECTS_ROOT",
        "audioformation.cli.PROJECTS_ROOT",
    ]
    for target in targets:
        try:
            monkeypatch.setattr(target, projects_root)
        except AttributeError:
            pass  # Module may not import PROJECTS_ROOT directly

    return projects_root


@pytest.fixture
def sample_project(tmp_path, isolate_projects):
    """
    Create a minimal valid project inside the isolated PROJECTS_ROOT.
    Uses the directory already created by isolate_projects.
    """
    from audioformation.config import PROJECT_DIRS

    projects_root = isolate_projects  # reuse, don't recreate
    project_id = "TEST_PROJECT"
    project_dir = projects_root / project_id
    project_dir.mkdir(exist_ok=True)

    # Create all subdirectories
    for subdir in PROJECT_DIRS:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Write minimal project.json
    project_json = {
        "id": project_id,
        "version": "1.0",
        "created": "2026-02-13T00:00:00Z",
        "languages": ["ar", "en"],
        "chapters": [
            {
                "id": "ch01",
                "title": "Test Chapter",
                "language": "ar",
                "source": "01_TEXT/chapters/ch01.txt",
                "character": "narrator",
                "mode": "single",
                "direction": {
                    "energy": "normal",
                    "pace": "moderate",
                    "emotion": "neutral"
                }
            }
        ],
        "characters": {
            "narrator": {
                "name": "Narrator",
                "engine": "edge",
                "voice": "ar-SA-HamedNeural",
                "persona": "Calm narrator",
                "reference_audio": None
            }
        },
        "generation": {
            "chunk_max_chars": 200,
            "chunk_strategy": "breath_group",
            "crossfade_ms": 120,
            "crossfade_min_ms": 50,
            "leading_silence_ms": 100,
            "max_retries_per_chunk": 3,
            "fail_threshold_percent": 5,
            "edge_tts_rate_limit_ms": 200,
            "edge_tts_concurrency": 4,
            "edge_tts_ssml": True,
            "fallback_scope": "chapter",
            "fallback_chain": ["edge", "gtts"],
            "crossfade_overrides": {
                "edge": 120,
                "xtts": 80,
                "gtts": 150
            }
        },
        "qc": {
            "snr_method": "vad_noise_floor",
            "snr_min_db": 20,
            "max_duration_deviation_percent": 30,
            "clipping_threshold_dbfs": -0.5,
            "lufs_deviation_max": 3,
            "pitch_jump_max_semitones": 12,
            "boundary_artifact_check": True
        },
        "mix": {
            "master_volume": 0.9,
            "target_lufs": -16,
            "true_peak_limit_dbtp": -1.0,
            "gap_between_chapters_sec": 2.0,
            "ducking": {
                "method": "vad",
                "vad_model": "silero-vad",
                "vad_threshold": 0.5,
                "vad_threshold_ar": 0.45,
                "look_ahead_ms": 200,
                "attack_ms": 100,
                "release_ms": 500,
                "attenuation_db": -12,
                "frequency_aware": False
            }
        },
        "export": {
            "formats": ["mp3"],
            "mp3_bitrate": 192,
            "m4b_aac_bitrate": 128,
            "include_cover_art": False,
            "cover_art": None,
            "chapter_transition": "silence",
            "chapter_transition_file": None,
            "metadata": {
                "author": "Test",
                "narrator": "Test",
                "publisher": "",
                "year": 2026,
                "description": ""
            }
        }
    }
    (project_dir / "project.json").write_text(
        json.dumps(project_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Write pipeline-status.json
    pipeline_status = {
        "project_id": project_id,
        "nodes": {
            "bootstrap": {"status": "complete", "timestamp": "2026-02-13T00:00:00Z"},
            "ingest": {"status": "pending"},
            "validate": {"status": "pending"},
            "generate": {"status": "pending"},
            "qc_scan": {"status": "pending"},
            "process": {"status": "pending"},
            "compose": {"status": "pending"},
            "mix": {"status": "pending"},
            "qc_final": {"status": "pending"},
            "export": {"status": "pending"}
        }
    }
    (project_dir / "pipeline-status.json").write_text(
        json.dumps(pipeline_status, indent=2),
        encoding="utf-8"
    )

    # Write a sample Arabic text file
    chapters_dir = project_dir / "01_TEXT" / "chapters"
    (chapters_dir / "ch01.txt").write_text(
        "مرحبا بالعالم. هذا فصل تجريبي للاختبار.",
        encoding="utf-8"
    )

    return {
        "id": project_id,
        "dir": project_dir,
        "projects_root": projects_root
    }


@pytest.fixture
def sample_project_with_text(sample_project):
    """
    Extends sample_project with multiple chapters already ingested.
    For tests that need text already in place (skip existing, etc).
    """
    project_dir = sample_project["dir"]
    chapters_dir = project_dir / "01_TEXT" / "chapters"

    # ch01.txt already exists from sample_project — Arabic
    # Add ch02 — English
    (chapters_dir / "ch02.txt").write_text(
        "The morning light filtered through the ancient windows. "
        "He stood there, contemplating the journey ahead. "
        "Every step would bring him closer to the truth.",
        encoding="utf-8"
    )

    # Add ch03 — Arabic, longer
    (chapters_dir / "ch03.txt").write_text(
        "في ذلك الصباح الباكر، كانت الشمس تشرق ببطء فوق المدينة القديمة. "
        "كان الهواء بارداً ومنعشاً، يحمل رائحة الياسمين من الحدائق المجاورة. "
        "وقف هناك يتأمل الأفق البعيد، يفكر في كل ما حدث.",
        encoding="utf-8"
    )

    # Update project.json with all three chapters
    import json
    project_json_path = project_dir / "project.json"
    config = json.loads(project_json_path.read_text(encoding="utf-8"))

    config["chapters"] = [
        {
            "id": "ch01",
            "title": "المقدمة",
            "language": "ar",
            "source": "01_TEXT/chapters/ch01.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {"energy": "normal", "pace": "moderate", "emotion": "neutral"}
        },
        {
            "id": "ch02",
            "title": "The Journey",
            "language": "en",
            "source": "01_TEXT/chapters/ch02.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {"energy": "normal", "pace": "moderate", "emotion": "neutral"}
        },
        {
            "id": "ch03",
            "title": "الفجر",
            "language": "ar",
            "source": "01_TEXT/chapters/ch03.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {"energy": "quiet contemplation", "pace": "slow", "emotion": "wonder"}
        },
    ]

    project_json_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Mark ingest as done
    status_path = project_dir / "pipeline-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["nodes"]["ingest"] = {"status": "complete", "timestamp": "2026-02-13T00:00:00Z"}
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    sample_project["chapters"] = ["ch01", "ch02", "ch03"]
    return sample_project