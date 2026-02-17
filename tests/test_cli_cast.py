"""Tests for the 'cast' CLI command group."""

import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from audioformation.cli import main
from audioformation.project import load_project_json


@pytest.fixture
def runner():
    return CliRunner()


def test_cast_list(runner, sample_project, isolate_projects):
    """Test listing characters."""
    result = runner.invoke(main, ["cast", "list", sample_project["id"]])
    assert result.exit_code == 0
    assert "Narrator" in result.output
    assert "edge" in result.output
    assert "ar-SA-HamedNeural" in result.output


def test_cast_add_new(runner, sample_project, isolate_projects):
    """Test adding a new character."""
    result = runner.invoke(
        main,
        [
            "cast",
            "add",
            sample_project["id"],
            "--id",
            "hero",
            "--name",
            "Hero Character",
            "--engine",
            "edge",
            "--voice",
            "en-US-GuyNeural",
            "--dialect",
            "msa",
        ],
    )

    assert result.exit_code == 0
    assert "Added character: hero" in result.output

    # Verify JSON
    pj = load_project_json(sample_project["id"])
    assert "hero" in pj["characters"]
    assert pj["characters"]["hero"]["name"] == "Hero Character"
    assert pj["characters"]["hero"]["voice"] == "en-US-GuyNeural"


def test_cast_update_existing(runner, sample_project, isolate_projects):
    """Test updating an existing character."""
    # Narrator exists from fixture
    result = runner.invoke(
        main,
        [
            "cast",
            "add",
            sample_project["id"],
            "--id",
            "narrator",
            "--name",
            "Updated Narrator",
            "--engine",
            "elevenlabs",
        ],
    )

    assert result.exit_code == 0
    assert "Updated character: narrator" in result.output

    pj = load_project_json(sample_project["id"])
    assert pj["characters"]["narrator"]["name"] == "Updated Narrator"
    assert pj["characters"]["narrator"]["engine"] == "elevenlabs"


def test_cast_clone_workflow(runner, sample_project, isolate_projects, tmp_path):
    """Test the clone command for XTTS setup."""
    # Create a dummy reference file outside the project
    ref_file = tmp_path / "original_ref.wav"
    ref_file.write_text("fake audio content")

    result = runner.invoke(
        main,
        [
            "cast",
            "clone",
            sample_project["id"],
            "--id",
            "cloned_hero",
            "--reference",
            str(ref_file),
        ],
    )

    assert result.exit_code == 0
    assert "Copied reference" in result.output
    # 'cloned_hero' is new, so it should be Created
    assert "Created character" in result.output

    # Verify file copy
    project_dir = sample_project["dir"]
    dest_path = project_dir / "02_VOICES" / "references" / "original_ref.wav"
    assert dest_path.exists()
    assert dest_path.read_text() == "fake audio content"

    # Verify JSON update
    pj = load_project_json(sample_project["id"])
    char = pj["characters"]["cloned_hero"]
    assert char["engine"] == "xtts"
    assert char["reference_audio"] == "02_VOICES/references/original_ref.wav"


def test_cast_clone_missing_file(runner, sample_project, isolate_projects):
    """Test clone with non-existent file."""
    result = runner.invoke(
        main,
        [
            "cast",
            "clone",
            sample_project["id"],
            "--id",
            "fail_hero",
            "--reference",
            "nonexistent.wav",
        ],
    )

    assert result.exit_code != 0
    # Click's default error message for type=Path(exists=True)
    assert "does not exist" in result.output
