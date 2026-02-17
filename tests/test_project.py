"""Tests for project CRUD operations."""

import json
from pathlib import Path

import pytest

from audioformation.project import (
    create_project,
    list_projects,
    load_project_json,
    load_pipeline_status,
    save_project_json,
    project_exists,
    get_project_path,
)
from audioformation.config import PROJECT_DIRS


class TestCreateProject:
    """Tests for project creation."""

    def test_creates_directory_structure(self, isolate_projects: Path) -> None:
        path = create_project("MY_NOVEL")

        assert path.exists()
        assert (path / "project.json").exists()
        assert (path / "pipeline-status.json").exists()
        assert (path / ".gitignore").exists()

        for dir_rel in PROJECT_DIRS:
            assert (path / dir_rel).exists(), f"Missing directory: {dir_rel}"

    def test_project_json_has_required_fields(self, isolate_projects: Path) -> None:
        create_project("FIELD_TEST")
        pj = load_project_json("FIELD_TEST")

        assert pj["id"] == "FIELD_TEST"
        assert pj["version"] == "1.0"
        assert "created" in pj
        assert pj["languages"] == ["ar", "en"]
        assert "chapters" in pj
        assert "characters" in pj
        assert "generation" in pj
        assert "qc" in pj
        assert "mix" in pj
        assert "export" in pj

    def test_pipeline_status_initialized(self, isolate_projects: Path) -> None:
        create_project("STATUS_TEST")
        ps = load_pipeline_status("STATUS_TEST")

        assert ps["project_id"] == "STATUS_TEST"
        assert "nodes" in ps

        for node_data in ps["nodes"].values():
            assert node_data["status"] == "pending"

    def test_duplicate_project_raises(self, isolate_projects: Path) -> None:
        create_project("DUPLICATE")

        with pytest.raises(FileExistsError):
            create_project("DUPLICATE")

    def test_sanitizes_project_id(self, isolate_projects: Path) -> None:
        path = create_project("My Novel 2026!")

        assert path.name == "MY_NOVEL_2026"

    def test_gitignore_content(self, isolate_projects: Path) -> None:
        path = create_project("GIT_TEST")
        gitignore = (path / ".gitignore").read_text()

        assert "engines.json" in gitignore
        assert "03_GENERATED" in gitignore
        assert "07_EXPORT" in gitignore
        assert ".gitkeep" in gitignore

    def test_gitkeep_files_created(self, isolate_projects: Path) -> None:
        path = create_project("KEEP_TEST")

        for dir_rel in PROJECT_DIRS:
            gitkeep = path / dir_rel / ".gitkeep"
            assert gitkeep.exists(), f"Missing .gitkeep in {dir_rel}"


class TestListProjects:
    """Tests for project listing."""

    def test_empty_when_no_projects(self, isolate_projects: Path) -> None:
        assert list_projects() == []

    def test_lists_created_projects(self, isolate_projects: Path) -> None:
        create_project("ALPHA")
        create_project("BETA")

        projects = list_projects()
        ids = [p["id"] for p in projects]

        assert "ALPHA" in ids
        assert "BETA" in ids
        assert len(projects) == 2

    def test_includes_chapter_count(
        self, sample_project_with_text, isolate_projects: Path
    ) -> None:
        projects = list_projects()
        project = next(p for p in projects if p["id"] == sample_project_with_text["id"])

        # sample_project_with_text has 3 chapters (ch01, ch02, ch03)
        assert project["chapters"] >= 2


class TestLoadSave:
    """Tests for JSON read/write."""

    def test_round_trip(self, sample_project) -> None:
        pj = load_project_json(sample_project["id"])
        pj["languages"] = ["ar", "en", "fr"]
        save_project_json(sample_project["id"], pj)

        reloaded = load_project_json(sample_project["id"])
        assert reloaded["languages"] == ["ar", "en", "fr"]

    def test_load_nonexistent_raises(self, isolate_projects: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_project_json("GHOST_PROJECT")


class TestProjectExists:
    """Tests for existence checks."""

    def test_exists_after_creation(self, sample_project) -> None:
        assert project_exists(sample_project["id"]) is True

    def test_not_exists(self, isolate_projects: Path) -> None:
        assert project_exists("NOPE") is False

    def test_invalid_id_returns_false(self, isolate_projects: Path) -> None:
        assert project_exists("../../../etc/passwd") is False
