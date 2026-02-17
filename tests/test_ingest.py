"""Tests for text ingestion pipeline."""

import json
import pytest
from pathlib import Path
from audioformation.ingest import ingest_text


class TestIngestText:
    def test_ingest_creates_chapters(self, sample_project, isolate_projects, tmp_path):
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

        result = ingest_text(sample_project["id"], source)

        assert result["ingested"] >= 1
        chapters_dir = sample_project["dir"] / "01_TEXT" / "chapters"
        assert (chapters_dir / "ch01.txt").exists()
        assert (chapters_dir / "ch02.txt").exists()

    def test_auto_detects_arabic(self, sample_project, isolate_projects, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch02.txt").write_text(
            "هذا نص عربي لاختبار الكشف التلقائي عن اللغة.",
            encoding="utf-8",
        )

        result = ingest_text(sample_project["id"], source)
        assert result["ingested"] >= 1

        config = json.loads(
            (sample_project["dir"] / "project.json").read_text(encoding="utf-8")
        )
        ar_chapters = [
            ch
            for ch in config.get("chapters", [])
            if ch.get("id") == "ch02" and ch.get("language") == "ar"
        ]
        assert len(ar_chapters) >= 1, (
            f"Expected Arabic ch02 in project.json. "
            f"Chapters: {config.get('chapters', [])}"
        )

    def test_auto_detects_english(self, sample_project, isolate_projects, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch02.txt").write_text(
            "This is English text for automatic language detection.",
            encoding="utf-8",
        )

        result = ingest_text(sample_project["id"], source)
        assert result["ingested"] >= 1

        config = json.loads(
            (sample_project["dir"] / "project.json").read_text(encoding="utf-8")
        )
        en_chapters = [
            ch
            for ch in config.get("chapters", [])
            if ch.get("id") == "ch02" and ch.get("language") == "en"
        ]
        assert len(en_chapters) >= 1, (
            f"Expected English ch02 in project.json. "
            f"Chapters: {config.get('chapters', [])}"
        )

    def test_language_override(self, sample_project, isolate_projects, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch02.txt").write_text("Some text.", encoding="utf-8")

        result = ingest_text(sample_project["id"], source, language="ar")
        assert result["ingested"] >= 1

        config = json.loads(
            (sample_project["dir"] / "project.json").read_text(encoding="utf-8")
        )
        ch02_entries = [
            ch for ch in config.get("chapters", []) if ch.get("id") == "ch02"
        ]
        assert len(ch02_entries) >= 1, "ch02 not found in project.json"
        assert (
            ch02_entries[0].get("language") == "ar"
        ), f"Expected language='ar' (override), got: {ch02_entries[0].get('language')}"

    def test_copies_files_to_project(self, sample_project, isolate_projects, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Hello world.", encoding="utf-8")

        ingest_text(sample_project["id"], source)

        dest = sample_project["dir"] / "01_TEXT" / "chapters" / "ch01.txt"
        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == "Hello world."

    def test_skips_existing_chapters(
        self, sample_project_with_text, isolate_projects, tmp_path
    ):
        # sample_project_with_text already has ch01, ch02, ch03
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Duplicate.", encoding="utf-8")
        (source / "ch04.txt").write_text("New chapter.", encoding="utf-8")

        result = ingest_text(sample_project_with_text["id"], source)

        assert result.get("skipped", 0) >= 1
        # ch04 should be new
        dest = sample_project_with_text["dir"] / "01_TEXT" / "chapters" / "ch04.txt"
        assert dest.exists()

    def test_updates_pipeline_status(self, sample_project, isolate_projects, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch01.txt").write_text("Test.", encoding="utf-8")

        ingest_text(sample_project["id"], source)

        status_file = sample_project["dir"] / "pipeline-status.json"
        status = json.loads(status_file.read_text(encoding="utf-8"))
        assert status["nodes"]["ingest"]["status"] == "complete"

    def test_missing_source_dir_raises(self, sample_project, isolate_projects):
        with pytest.raises(FileNotFoundError):
            ingest_text(sample_project["id"], Path("/nonexistent/path"))

    def test_empty_source_dir_raises(self, sample_project, isolate_projects, tmp_path):
        source = tmp_path / "empty"
        source.mkdir()

        with pytest.raises(
            ValueError, match="[Nn]o .txt files|[Nn]o text files|[Ee]mpty"
        ):
            ingest_text(sample_project["id"], source)

    def test_detects_diacritization_level(
        self, sample_project, isolate_projects, tmp_path
    ):
        source = tmp_path / "source"
        source.mkdir()
        (source / "ch02.txt").write_text(
            "بسم الله الرحمن الرحيم",
            encoding="utf-8",
        )

        result = ingest_text(sample_project["id"], source)
        assert result["ingested"] >= 1

        from audioformation.utils.arabic import detect_diacritization_level

        text = (sample_project["dir"] / "01_TEXT" / "chapters" / "ch02.txt").read_text(
            encoding="utf-8"
        )
        level = detect_diacritization_level(text)
        assert level < 0.1, f"Expected undiacritized text, got level: {level}"
