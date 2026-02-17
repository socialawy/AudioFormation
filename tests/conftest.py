"""Shared test fixtures for AudioFormation."""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Fix ModuleNotFoundError when running locally without editable install
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

# ──────────────────────────────────────────────────────────────
# Eager Dependency Mocking
# ──────────────────────────────────────────────────────────────
# We must mock missing dependencies at the top level (before fixtures)
# so that pytest can collect tests without ImportErrors.

MODULES_TO_MOCK = [
    "edge_tts",
    "soundfile",
    "pyloudnorm",
    "pydub",
    "pydub.AudioSegment",
    "numpy",
    "scipy",
    "scipy.io",
    "scipy.io.wavfile",
    "mishkal",
    "mishkal.tashkeel",
    "gtts",
]

for mod_name in MODULES_TO_MOCK:
    try:
        __import__(mod_name)
    except ImportError:
        # Create a mock module
        mock_mod = MagicMock()

        # ── Specific Mock Behaviors ──

        if mod_name == "edge_tts":
            mock_mod.Communicate = MagicMock()
            # Communicate.save needs to act awaitable and create file with content
            async def _save(path):
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"MOCK_MP3_DATA" * 10)  # Non-zero size

            mock_mod.Communicate.return_value.save = _save
            mock_mod.list_voices = MagicMock(return_value=[])

        elif mod_name == "soundfile":
            # Check if real soundfile is available
            real_soundfile = None
            try:
                import soundfile as real_sf

                if not isinstance(real_sf, MagicMock):
                    real_soundfile = real_sf
            except ImportError:
                pass

            if real_soundfile:
                # Use real soundfile functions
                mock_mod.read = real_soundfile.read
                mock_mod.write = real_soundfile.write
                mock_mod.info = real_soundfile.info
            else:
                # Check for real numpy to avoid __array__ errors
                real_numpy = None
                try:
                    import numpy as np

                    if not isinstance(np, MagicMock):
                        real_numpy = np
                except ImportError:
                    pass

                if real_numpy:
                    # Return real array to satisfy real numpy functions
                    def _mock_read_real(*args, **kwargs):
                        # Default: 1 second of silence
                        return real_numpy.zeros(24000, dtype=real_numpy.float32), 24000

                    mock_mod.read = MagicMock(side_effect=_mock_read_real)
                else:
                    # Return mock array
                    mock_data = MagicMock()
                    mock_data.ndim = 1
                    mock_data.shape = (24000,)
                    mock_data.__len__.return_value = 24000
                    mock_data.__array__ = lambda *args: [0.0] * 24000
                    mock_mod.read = MagicMock(return_value=(mock_data, 24000))

                # sf.write -> create file with content
                def _write(file, data, samplerate, **kwargs):
                    p = Path(file)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    # Write enough bytes to pass checks > 1000 bytes
                    p.write_bytes(b"MOCK_WAV_DATA" * 100)

                mock_mod.write = MagicMock(side_effect=_write)

                # sf.info -> duration
                mock_info = MagicMock()
                mock_info.duration = 5.0
                mock_info.samplerate = 24000
                mock_mod.info.return_value = mock_info

        elif mod_name == "pyloudnorm":
            # pyln.Meter().integrated_loudness() -> float
            mock_meter = MagicMock()
            mock_meter.integrated_loudness.return_value = -16.0
            mock_mod.Meter.return_value = mock_meter

        elif mod_name == "pydub":
            # AudioSegment instance mock
            mock_segment = MagicMock()
            mock_segment.__len__.return_value = 5000  # 5000 ms
            mock_segment.duration_seconds = 5.0

            # export writes bytes to path
            def _export(path, **k):
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                # Default size
                p.write_bytes(b"MOCK_EXPORT_DATA" * 50)

            mock_segment.export.side_effect = _export

            # Support addition (concatenation) and return SELF
            # IMPORTANT: __iadd__ must return self to preserve the mock instance
            # with the side_effect during operations like `combined += chunk`
            mock_segment.__add__.return_value = mock_segment
            mock_segment.__radd__.return_value = mock_segment
            mock_segment.__iadd__.return_value = mock_segment
            mock_segment.append.return_value = mock_segment

            mock_mod.AudioSegment = MagicMock()

            # CRITICAL: from_file MUST raise FileNotFoundError if file missing
            # This enables negative testing in test_export.py
            def _from_file(path, **kwargs):
                if not Path(path).exists():
                    raise FileNotFoundError(f"File not found: {path}")
                return mock_segment

            mock_mod.AudioSegment.from_file.side_effect = _from_file
            mock_mod.AudioSegment.from_mp3.side_effect = _from_file

            # silent/empty return the mock segment directly
            mock_mod.AudioSegment.silent.return_value = mock_segment
            mock_mod.AudioSegment.empty.return_value = mock_segment

        elif mod_name == "numpy":
            # Basic numpy support for tests that might use it
            mock_mod.zeros.return_value = MagicMock()
            mock_mod.linspace.return_value = MagicMock()
            mock_mod.sin.return_value = MagicMock()
            mock_mod.max.return_value = 1.0
            mock_mod.abs.return_value = MagicMock()
            mock_mod.float32 = float
            mock_mod.float64 = float

        elif mod_name == "mishkal.tashkeel":
            # Correctly mock the TashkeelClass class INSIDE mishkal.tashkeel module
            mock_tashkeel_inst = MagicMock()

            # Force return python string with ACTUAL diacritics for detection
            def _tashkeel(text):
                if isinstance(text, str):
                    # Append a Fatha (U+064E) to ensure detection sees it as diacritized
                    return text + "\u064E"
                return "diacritized_text\u064E"

            mock_tashkeel_inst.tashkeel.side_effect = _tashkeel
            mock_mod.TashkeelClass.return_value = mock_tashkeel_inst

        sys.modules[mod_name] = mock_mod


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


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
        "audioformation.audio.composer.PROJECTS_ROOT",
    ]
    for target in targets:
        try:
            monkeypatch.setattr(target, projects_root)
        except (ImportError, AttributeError):
            pass

    return projects_root


@pytest.fixture
def sample_project(tmp_path, isolate_projects):
    """
    Create a minimal valid project inside the isolated PROJECTS_ROOT.
    """
    from audioformation.config import PROJECT_DIRS

    projects_root = isolate_projects
    project_id = "TEST_PROJECT"
    project_dir = projects_root / project_id
    project_dir.mkdir(exist_ok=True)

    for subdir in PROJECT_DIRS:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

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
                    "emotion": "neutral",
                },
            }
        ],
        "characters": {
            "narrator": {
                "name": "Narrator",
                "engine": "edge",
                "voice": "ar-SA-HamedNeural",
                "persona": "Calm narrator",
                "reference_audio": None,
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
            "crossfade_overrides": {"edge": 120, "xtts": 80, "gtts": 150},
        },
        "qc": {
            "snr_method": "vad_noise_floor",
            "snr_min_db": 20,
            "max_duration_deviation_percent": 30,
            "clipping_threshold_dbfs": -0.5,
            "lufs_deviation_max": 3,
            "pitch_jump_max_semitones": 12,
            "boundary_artifact_check": True,
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
                "frequency_aware": False,
            },
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
                "description": "",
            },
        },
    }
    (project_dir / "project.json").write_text(
        json.dumps(project_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

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
            "export": {"status": "pending"},
        },
    }
    (project_dir / "pipeline-status.json").write_text(
        json.dumps(pipeline_status, indent=2), encoding="utf-8"
    )

    chapters_dir = project_dir / "01_TEXT" / "chapters"
    (chapters_dir / "ch01.txt").write_text(
        "مرحبا بالعالم. هذا فصل تجريبي للاختبار.", encoding="utf-8"
    )

    return {"id": project_id, "dir": project_dir, "projects_root": projects_root}


@pytest.fixture
def sample_project_with_text(sample_project):
    """Extends sample_project with multiple chapters already ingested."""
    project_dir = sample_project["dir"]
    chapters_dir = project_dir / "01_TEXT" / "chapters"

    (chapters_dir / "ch02.txt").write_text(
        "The morning light filtered through the ancient windows.", encoding="utf-8"
    )
    (chapters_dir / "ch03.txt").write_text(
        "في ذلك الصباح الباكر، كانت الشمس تشرق ببطء.", encoding="utf-8"
    )

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
            "direction": {"energy": "normal", "pace": "moderate", "emotion": "neutral"},
        },
        {
            "id": "ch02",
            "title": "The Journey",
            "language": "en",
            "source": "01_TEXT/chapters/ch02.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {"energy": "normal", "pace": "moderate", "emotion": "neutral"},
        },
        {
            "id": "ch03",
            "title": "الفجر",
            "language": "ar",
            "source": "01_TEXT/chapters/ch03.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {
                "energy": "quiet contemplation",
                "pace": "slow",
                "emotion": "wonder",
            },
        },
    ]

    project_json_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    status_path = project_dir / "pipeline-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["nodes"]["ingest"] = {
        "status": "complete",
        "timestamp": "2026-02-13T00:00:00Z",
    }
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    sample_project["chapters"] = ["ch01", "ch02", "ch03"]
    return sample_project
