"""Tests for text ingestion pipeline."""

import pytest
from pathlib import Path

from audioformation.ingest import ingest_text
from audioformation.project import load_project_json, load_pipeline_status


class TestIngestText:
    """Tests for the text ingestion node."""

    def test_ingest_creates_chapters(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        # Create source directory with text files
        source = tmp_path / "source_chapters"
        source.mkdir()
        (source / "ch01.txt").write_text(
            "بسم الله الرحمن الرحيم. هذا الفصل الأول.",
            encoding="utf-8",
        )
        (source / "ch02.txt").write_text(
            "This is the second chapter. It is in English.",
            encoding="utf-8",
        )

        result = ingest_text(sample_project, source)

        assert result["ingested"] == 2
        assert result["total_files"] == 2

        pj = load_project_json(sample_project)
        assert len(pj["chapters"]) == 2

    def test_auto_detects_arabic(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text(
            "هذا نص عربي لاختبار الكشف التلقائي عن اللغة.",
            encoding="utf-8",
        )

        result = ingest_text(sample_project, source)

        details = result["details"]
        assert details[0]["language"] == "ar"

    def test_auto_detects_english(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text(
            "This is English text for automatic language detection.",
            encoding="utf-8",
        )

        result = ingest_text(sample_project, source)
        assert result["details"][0]["language"] == "en"

    def test_language_override(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Some text.", encoding="utf-8")

        result = ingest_text(sample_project, source, language="ar")
        assert result["details"][0]["language"] == "ar"

    def test_copies_files_to_project(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Hello world.", encoding="utf-8")

        ingest_text(sample_project, source)

        project_path = isolate_projects / sample_project
        copied = project_path / "01_TEXT" / "chapters" / "ch01.txt"
        assert copied.exists()
        assert copied.read_text(encoding="utf-8") == "Hello world."

    def test_skips_existing_chapters(
        self, sample_project_with_text: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        # sample_project_with_text already has ch01 and ch02
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Duplicate.", encoding="utf-8")
        (source / "ch03.txt").write_text("New chapter.", encoding="utf-8")

        result = ingest_text(sample_project_with_text, source)

        assert result["skipped"] == 1  # ch01 already exists
        assert result["ingested"] == 1  # ch03 is new

    def test_updates_pipeline_status(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Test.", encoding="utf-8")

        ingest_text(sample_project, source)

        ps = load_pipeline_status(sample_project)
        assert ps["nodes"]["ingest"]["status"] == "complete"

    def test_missing_source_dir_raises(
        self, sample_project: str, isolate_projects: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            ingest_text(sample_project, Path("/nonexistent/path"))

    def test_empty_source_dir_raises(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "empty"
        source.mkdir()

        with pytest.raises(ValueError, match="No .txt files"):
            ingest_text(sample_project, source)

    def test_detects_diacritization_level(
        self, sample_project: str, isolate_projects: Path, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text(
            "بسم الله الرحمن الرحيم",  # undiacritized
            encoding="utf-8",
        )

        result = ingest_text(sample_project, source)
        assert result["details"][0]["diacritization"] == "undiacritized"