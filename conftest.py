"""Shared pytest fixtures for AudioFormation tests."""

import json
import shutil
from pathlib import Path

import pytest

from audioformation.config import PROJECTS_ROOT


@pytest.fixture(autouse=True)
def isolate_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Redirect PROJECTS_ROOT to a temp directory for every test.

    Prevents tests from touching the real filesystem.
    Returns the temporary projects root.
    """
    test_root = tmp_path / "PROJECTS"
    test_root.mkdir()

    # Monkeypatch the config module's PROJECTS_ROOT
    import audioformation.config as cfg
    monkeypatch.setattr(cfg, "PROJECTS_ROOT", test_root)

    # Also patch it in project.py (which imports it at module level)
    import audioformation.project as proj_mod
    monkeypatch.setattr(proj_mod, "PROJECTS_ROOT", test_root)

    return test_root


@pytest.fixture
def sample_project(isolate_projects: Path) -> str:
    """Create a minimal sample project and return its ID."""
    from audioformation.project import create_project

    project_id = "TEST_PROJECT"
    create_project(project_id)
    return project_id


@pytest.fixture
def sample_project_with_text(sample_project: str, isolate_projects: Path) -> str:
    """
    Create a sample project with Arabic and English chapter text files,
    and update project.json with chapter entries.
    """
    from audioformation.project import load_project_json, save_project_json

    project_id = sample_project
    project_path = isolate_projects / project_id

    # Write sample text files
    chapters_dir = project_path / "01_TEXT" / "chapters"

    (chapters_dir / "ch01.txt").write_text(
        "بسم الله الرحمن الرحيم. في البدء كان الكلمة، والكلمة كانت عند الله.\n"
        "هذا الفصل الأول من الرواية.",
        encoding="utf-8",
    )

    (chapters_dir / "ch02.txt").write_text(
        "In the beginning was the word. This is the second chapter.\n"
        "It continues with more text here.",
        encoding="utf-8",
    )

    # Update project.json with chapters
    pj = load_project_json(project_id)
    pj["chapters"] = [
        {
            "id": "ch01",
            "title": "المقدمة",
            "language": "ar",
            "source": "01_TEXT/chapters/ch01.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {
                "energy": "quiet contemplation",
                "pace": "slow",
                "emotion": "wonder",
            },
        },
        {
            "id": "ch02",
            "title": "The Beginning",
            "language": "en",
            "source": "01_TEXT/chapters/ch02.txt",
            "character": "narrator",
            "mode": "single",
            "direction": {
                "energy": "normal",
                "pace": "moderate",
                "emotion": "neutral",
            },
        },
    ]
    save_project_json(project_id, pj)

    return project_id