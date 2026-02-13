"""
Validation gates — hard checks before generation, mixing, export.

Node 2 (Validate): HARD GATE
- project.json against JSON Schema
- Text files exist + non-empty
- Characters defined + voices assigned
- Engine available
- Arabic diacritics status
- LUFS target defined
- ffmpeg available
"""

import json
from pathlib import Path
from typing import Any

from audioformation.project import load_project_json, get_project_path


# ──────────────────────────────────────────────
# Schema path
# ──────────────────────────────────────────────

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "schemas" / "project.schema.json"


class ValidationResult:
    """Collects validation pass/warn/fail results."""

    def __init__(self) -> None:
        self.passed: list[str] = []
        self.warnings: list[str] = []
        self.failures: list[str] = []

    def pass_(self, msg: str) -> None:
        self.passed.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.failures) == 0

    def summary(self) -> dict[str, Any]:
        return {
            "passed": len(self.passed),
            "warnings": len(self.warnings),
            "failures": len(self.failures),
            "ok": self.ok,
            "details": {
                "passed": self.passed,
                "warnings": self.warnings,
                "failures": self.failures,
            },
        }


def validate_project(project_id: str) -> ValidationResult:
    """
    Run the Node 2 HARD GATE validation.

    Checks everything needed before generation can proceed.
    """
    result = ValidationResult()
    project_path = get_project_path(project_id)

    try:
        pj = load_project_json(project_id)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        result.fail(f"Cannot load project.json: {e}")
        return result

    _check_schema(pj, result)
    _check_text_files(pj, project_path, result)
    _check_characters(pj, project_path, result)
    _check_arabic_diacritics(pj, project_path, result)
    _check_dialect_voice(pj, result)
    _check_generation_config(pj, result)
    _check_mix_config(pj, result)
    _check_ffmpeg(result)

    return result


# ──────────────────────────────────────────────
# Schema validation
# ──────────────────────────────────────────────


def _check_schema(pj: dict[str, Any], result: ValidationResult) -> None:
    """Validate project.json against the JSON schema."""
    try:
        import jsonschema

        if _SCHEMA_PATH.exists():
            schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(pj, schema)
            result.pass_("project.json passes schema validation.")
        else:
            result.warn("Schema file not found — skipping schema validation.")

    except jsonschema.ValidationError as e:
        # Extract a readable path
        path_str = " → ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        result.fail(f"Schema error at '{path_str}': {e.message}")

    except ImportError:
        result.warn("jsonschema not installed — skipping schema validation.")


# ──────────────────────────────────────────────
# Text file checks
# ──────────────────────────────────────────────


def _check_text_files(
    pj: dict[str, Any], project_path: Path, result: ValidationResult
) -> None:
    """Verify all chapter text files exist and are non-empty."""
    chapters = pj.get("chapters", [])

    if not chapters:
        result.fail("No chapters defined in project.json.")
        return

    for i, ch in enumerate(chapters):
        # Defensive: ensure chapter entry is a dict
        if not isinstance(ch, dict):
            result.fail(
                f"Chapter at index {i} is malformed (type={type(ch).__name__}, "
                f"expected dict). Check project.json."
            )
            continue

        ch_id = ch.get("id", "unknown")
        source = ch.get("source", "")

        if not source:
            result.fail(f"Chapter '{ch_id}': no source file specified.")
            continue

        source_path = project_path / source
        if not source_path.exists():
            result.fail(f"Chapter '{ch_id}': source file not found: {source}")
            continue

        content = source_path.read_text(encoding="utf-8").strip()
        if not content:
            result.fail(f"Chapter '{ch_id}': source file is empty: {source}")
            continue

        result.pass_(f"Chapter '{ch_id}': text file OK ({len(content)} chars).")

        lang = ch.get("language")
        if not lang:
            result.warn(f"Chapter '{ch_id}': no language tag specified.")


# ──────────────────────────────────────────────
# Character checks
# ──────────────────────────────────────────────


def _check_characters(
    pj: dict[str, Any], project_path: Path, result: ValidationResult
) -> None:
    """Verify characters are defined with voices and reference audio."""
    characters = pj.get("characters", {})

    if not characters:
        result.fail("No characters defined in project.json.")
        return

    for char_id, char_data in characters.items():
        engine = char_data.get("engine")
        voice = char_data.get("voice")
        ref_audio = char_data.get("reference_audio")

        if not engine:
            result.fail(f"Character '{char_id}': no engine specified.")
            continue

        if engine in ("edge", "elevenlabs", "openai-tts", "gemini-tts"):
            if not voice:
                result.fail(f"Character '{char_id}': engine '{engine}' requires a voice ID.")
            else:
                result.pass_(f"Character '{char_id}': voice '{voice}' on engine '{engine}'.")

        elif engine == "xtts":
            if not ref_audio:
                result.fail(f"Character '{char_id}': XTTS engine requires reference_audio.")
            else:
                ref_path = project_path / ref_audio
                if not ref_path.exists():
                    result.fail(
                        f"Character '{char_id}': reference audio not found: {ref_audio}"
                    )
                else:
                    result.pass_(f"Character '{char_id}': XTTS with reference '{ref_audio}'.")

        else:
            result.warn(f"Character '{char_id}': unknown engine '{engine}'.")

    # Check chapter→character references
    chapters = pj.get("chapters", [])
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            continue  # Already caught by _check_text_files

        ch_id = ch.get("id", "unknown")
        mode = ch.get("mode", "single")

        if mode == "single":
            ch_char = ch.get("character")
            if ch_char and ch_char not in characters:
                result.fail(f"Chapter '{ch_id}': references unknown character '{ch_char}'.")
        elif mode == "multi":
            default_char = ch.get("default_character")
            if default_char and default_char not in characters:
                result.fail(f"Chapter '{ch_id}': default_character '{default_char}' not found.")


# ──────────────────────────────────────────────
# Arabic-specific checks
# ──────────────────────────────────────────────


def _check_arabic_diacritics(
    pj: dict[str, Any], project_path: Path, result: ValidationResult
) -> None:
    """Check diacritization status for Arabic chapters."""
    from audioformation.utils.arabic import classify_diacritization

    chapters = pj.get("chapters", [])

    for ch in chapters:
        if ch.get("language") != "ar":
            continue

        ch_id = ch.get("id", "unknown")
        source = ch.get("source", "")
        source_path = project_path / source

        if not source_path.exists():
            continue  # Already caught by _check_text_files

        text = source_path.read_text(encoding="utf-8").strip()
        level = classify_diacritization(text)

        if level == "diacritized":
            result.pass_(f"Chapter '{ch_id}': Arabic text is diacritized.")
        elif level == "partial":
            result.warn(
                f"Chapter '{ch_id}': Arabic text is partially diacritized. "
                f"Consider running auto-diacritization for better TTS quality."
            )
        else:
            result.warn(
                f"Chapter '{ch_id}': Arabic text is undiacritized. "
                f"TTS quality may be degraded. Run auto-diacritization or "
                f"provide a diacritized version."
            )


def _check_dialect_voice(pj: dict[str, Any], result: ValidationResult) -> None:
    """Check dialect-voice pairing for all characters."""
    from audioformation.utils.arabic import validate_dialect_voice_match

    characters = pj.get("characters", {})

    for char_id, char_data in characters.items():
        dialect = char_data.get("dialect")
        voice = char_data.get("voice")

        warning = validate_dialect_voice_match(dialect, voice)
        if warning:
            result.warn(f"Character '{char_id}': {warning}")


# ──────────────────────────────────────────────
# Config checks
# ──────────────────────────────────────────────


def _check_generation_config(pj: dict[str, Any], result: ValidationResult) -> None:
    """Verify generation configuration is sane."""
    gen = pj.get("generation", {})

    if not gen:
        result.fail("No generation config in project.json.")
        return

    chunk_max = gen.get("chunk_max_chars", 0)
    if chunk_max < 50:
        result.warn(f"chunk_max_chars={chunk_max} is very small (min recommended: 50).")
    elif chunk_max > 500:
        result.warn(f"chunk_max_chars={chunk_max} is large — may cause XTTS quality issues.")

    crossfade = gen.get("crossfade_ms", 0)
    crossfade_min = gen.get("crossfade_min_ms", 50)
    if crossfade < crossfade_min:
        result.warn(
            f"crossfade_ms={crossfade} is below crossfade_min_ms={crossfade_min}. "
            f"Arabic coarticulation may produce audible boundaries."
        )

    result.pass_("Generation config present.")


def _check_mix_config(pj: dict[str, Any], result: ValidationResult) -> None:
    """Verify mix/LUFS target is defined."""
    mix = pj.get("mix", {})
    target_lufs = mix.get("target_lufs")

    if target_lufs is None:
        result.fail("No target_lufs defined in mix config.")
    else:
        result.pass_(f"LUFS target: {target_lufs}")

    true_peak = mix.get("true_peak_limit_dbtp")
    if true_peak is None:
        result.warn("No true_peak_limit defined in mix config.")


def _check_ffmpeg(result: ValidationResult) -> None:
    """Verify ffmpeg is available."""
    from audioformation.utils.hardware import detect_ffmpeg

    ff = detect_ffmpeg()
    if ff["ffmpeg_available"]:
        result.pass_(f"ffmpeg found: {ff['ffmpeg_path']}")
    else:
        result.fail("ffmpeg not found on PATH. Required for audio processing and export.")