"""
Global configuration, constants, and path resolution.

All magic numbers and default values live here.
Pipeline code imports from config — never hardcodes.
"""

from pathlib import Path
from typing import Final

# ──────────────────────────────────────────────
# Directory Layout
# ──────────────────────────────────────────────

PROJECTS_ROOT: Final[Path] = Path("PROJECTS")

PROJECT_DIRS: Final[list[str]] = [
    "00_CONFIG",
    "01_TEXT/chapters",
    "02_VOICES/references",
    "03_GENERATED/raw",
    "03_GENERATED/processed",
    "03_GENERATED/compare",
    "04_SFX/procedural",
    "04_SFX/samples",
    "05_MUSIC/generated",
    "05_MUSIC/imported",
    "05_MUSIC/midi",
    "06_MIX/sessions",
    "06_MIX/renders",
    "07_EXPORT/audiobook",
    "07_EXPORT/chapters",
]

# ──────────────────────────────────────────────
# Pipeline Nodes (ordered)
# ──────────────────────────────────────────────

PIPELINE_NODES: Final[list[str]] = [
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

HARD_GATES: Final[set[str]] = {"validate", "qc_final"}
AUTO_GATES: Final[set[str]] = {"qc_scan"}

# ──────────────────────────────────────────────
# Generation Defaults
# ──────────────────────────────────────────────

DEFAULT_CHUNK_MAX_CHARS: Final[int] = 200
DEFAULT_CROSSFADE_MS: Final[int] = 120
DEFAULT_CROSSFADE_MIN_MS: Final[int] = 50
DEFAULT_LEADING_SILENCE_MS: Final[int] = 100
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_FAIL_THRESHOLD_PCT: Final[float] = 5.0
DEFAULT_EDGE_RATE_LIMIT_MS: Final[int] = 200
DEFAULT_EDGE_CONCURRENCY: Final[int] = 4

# ──────────────────────────────────────────────
# QC Defaults
# ──────────────────────────────────────────────

DEFAULT_SNR_MIN_DB: Final[float] = 20.0
DEFAULT_MAX_DURATION_DEVIATION_PCT: Final[float] = 30.0
DEFAULT_CLIPPING_THRESHOLD_DBFS: Final[float] = -0.5
DEFAULT_LUFS_DEVIATION_MAX: Final[float] = 3.0
DEFAULT_PITCH_JUMP_MAX_ST: Final[float] = 12.0

# ──────────────────────────────────────────────
# Mix Defaults
# ──────────────────────────────────────────────

DEFAULT_TARGET_LUFS: Final[float] = -16.0
DEFAULT_TRUE_PEAK_LIMIT: Final[float] = -1.0
DEFAULT_CHAPTER_GAP_SEC: Final[float] = 2.0

DEFAULT_VAD_THRESHOLD: Final[float] = 0.50
DEFAULT_VAD_THRESHOLD_AR: Final[float] = 0.45
DEFAULT_DUCK_LOOK_AHEAD_MS: Final[int] = 200
DEFAULT_DUCK_ATTACK_MS: Final[int] = 100
DEFAULT_DUCK_RELEASE_MS: Final[int] = 500
DEFAULT_DUCK_ATTENUATION_DB: Final[float] = -12.0

# ──────────────────────────────────────────────
# Export Defaults
# ──────────────────────────────────────────────

DEFAULT_MP3_BITRATE: Final[int] = 192
DEFAULT_M4B_AAC_BITRATE: Final[int] = 128

COVER_ART_MIN_PX: Final[int] = 1400
COVER_ART_MAX_PX: Final[int] = 3000

# ──────────────────────────────────────────────
# Server
# ──────────────────────────────────────────────

API_PORT: Final[int] = 4001

# ──────────────────────────────────────────────
# XTTS
# ──────────────────────────────────────────────

DEFAULT_XTTS_TEMPERATURE: Final[float] = 0.7
DEFAULT_XTTS_REPETITION_PENALTY: Final[float] = 5.0
XTTS_MIN_VRAM_GB: Final[float] = 4.0

VRAM_STRATEGY_THRESHOLDS: Final[dict[str, float]] = {
    "conservative": 3.5,   # < 3.5 GB
    "empty_cache": 4.0,    # 4–6 GB
    "comfortable": 6.0,    # > 6 GB
}

# ──────────────────────────────────────────────
# Arabic
# ──────────────────────────────────────────────

DIACRITIZATION_UNDIACRITIZED: Final[float] = 0.05
DIACRITIZATION_PARTIAL: Final[float] = 0.30

DIALECT_VOICE_MAP: Final[dict[str, list[str]]] = {
    "msa": ["ar-SA-HamedNeural", "ar-SA-ZariyahNeural"],
    "eg":  ["ar-EG-SalmaNeural", "ar-EG-ShakirNeural"],
    "ae":  ["ar-AE-FatimaNeural", "ar-AE-HamdanNeural"],
    "sa":  ["ar-SA-HamedNeural", "ar-SA-ZariyahNeural"],
}