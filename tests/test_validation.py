"""Tests for the validation gate (Node 2)."""

import pytest
from pathlib import Path

from audioformation.validation import validate_project, ValidationResult
from audioformation.project import load_project_json, save_project_json


class TestValidationResult:
    """Tests for the ValidationResult data structure."""

    def test_empty_result_is_ok(self) -> None:
        r = ValidationResult()
        assert r.ok is True

    def test_failure_makes_not_ok(self) -> None:
        r = ValidationResult()
        r.fail("something broke")
        assert r.ok is False

    def test_warning_still_ok(self) -> None:
        r = ValidationResult()
        r.warn("minor issue")
        assert r.ok is True

    def test_summary_counts(self) -> None:
        r = ValidationResult()
        r.pass_("good")
        r.pass_("also good")
        r.warn("meh")
        r.fail("bad")

        s = r.summary()
        assert s["passed"] == 2
        assert s["warnings"] == 1
        assert s["failures"] == 1
        assert s["ok"] is False


class TestValidateProject:
    """Tests for the full validation gate."""

    def test_valid_project_passes(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        result = validate_project(sample_project_with_text)
        # Should pass text and character checks at minimum
        assert result.ok is True or len(result.failures) == 0

    def test_no_chapters_fails(
        self, sample_project: str, isolate_projects: Path
    ) -> None:
        # sample_project has no chapters
        result = validate_project(sample_project)
        assert result.ok is False
        assert any("No chapters" in f for f in result.failures)

    def test_missing_source_file_fails(
        self, sample_project: str, isolate_projects: Path
    ) -> None:
        pj = load_project_json(sample_project)
        pj["chapters"] = [{
            "id": "ch01",
            "title": "Test",
            "language": "en",
            "source": "01_TEXT/chapters/nonexistent.txt",
            "character": "narrator",
            "mode": "single",
        }]
        save_project_json(sample_project, pj)

        result = validate_project(sample_project)
        assert result.ok is False
        assert any("not found" in f for f in result.failures)

    def test_empty_source_file_fails(
        self, sample_project: str, isolate_projects: Path
    ) -> None:
        project_path = isolate_projects / sample_project
        ch_path = project_path / "01_TEXT" / "chapters" / "ch01.txt"
        ch_path.write_text("", encoding="utf-8")  # Empty

        pj = load_project_json(sample_project)
        pj["chapters"] = [{
            "id": "ch01",
            "title": "Test",
            "language": "en",
            "source": "01_TEXT/chapters/ch01.txt",
            "character": "narrator",
            "mode": "single",
        }]
        save_project_json(sample_project, pj)

        result = validate_project(sample_project)
        assert result.ok is False
        assert any("empty" in f for f in result.failures)

    def test_unknown_character_reference_fails(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        pj = load_project_json(sample_project_with_text)
        pj["chapters"][0]["character"] = "ghost_character"
        save_project_json(sample_project_with_text, pj)

        result = validate_project(sample_project_with_text)
        assert any("ghost_character" in f for f in result.failures)

    def test_xtts_without_reference_fails(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        pj = load_project_json(sample_project_with_text)
        pj["characters"]["narrator"]["engine"] = "xtts"
        pj["characters"]["narrator"]["reference_audio"] = None
        save_project_json(sample_project_with_text, pj)

        result = validate_project(sample_project_with_text)
        assert any("reference_audio" in f for f in result.failures)

    def test_arabic_diacritics_warning(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        result = validate_project(sample_project_with_text)
        # ch01 is Arabic, undiacritized — should produce a warning
        assert any("diacritiz" in w.lower() for w in result.warnings)

    def test_no_lufs_target_fails(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        pj = load_project_json(sample_project_with_text)
        del pj["mix"]["target_lufs"]
        save_project_json(sample_project_with_text, pj)

        result = validate_project(sample_project_with_text)
        assert any("target_lufs" in f for f in result.failures)

    def test_dialect_voice_mismatch_warns(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        pj = load_project_json(sample_project_with_text)
        pj["characters"]["narrator"]["dialect"] = "eg"
        pj["characters"]["narrator"]["voice"] = "ar-SA-HamedNeural"
        save_project_json(sample_project_with_text, pj)

        result = validate_project(sample_project_with_text)
        assert any("dialect" in w.lower() or "eg" in w.lower() for w in result.warnings)

    def test_crossfade_below_min_warns(
        self, sample_project_with_text: str, isolate_projects: Path
    ) -> None:
        pj = load_project_json(sample_project_with_text)
        pj["generation"]["crossfade_ms"] = 20
        pj["generation"]["crossfade_min_ms"] = 50
        save_project_json(sample_project_with_text, pj)

        result = validate_project(sample_project_with_text)
        assert any("crossfade" in w.lower() for w in result.warnings)