"""Tests for M4B audiobook export."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from audioformation.export.m4b import export_project_m4b, _generate_ffmetadata


@pytest.fixture
def setup_mixed_files(sample_project, tmp_path):
    """Create mock mixed chapter files."""
    mix_dir = sample_project["dir"] / "06_MIX" / "renders"
    mix_dir.mkdir(parents=True, exist_ok=True)

    (mix_dir / "ch01.wav").touch()
    (mix_dir / "ch02.wav").touch()

    return sample_project


def test_ffmetadata_format():
    """Test metadata text generation."""
    chapters = [
        {"title": "Chapter 1", "start": 0, "end": 1000},
        {"title": "Chapter 2", "start": 1000, "end": 2500},
    ]
    meta = _generate_ffmetadata(chapters, "My Book", "Author", "2026", "Narrator")

    assert ";FFMETADATA1" in meta
    assert "title=My Book" in meta
    assert "artist=Author" in meta
    assert "[CHAPTER]" in meta
    assert "START=0" in meta
    assert "END=1000" in meta
    assert "title=Chapter 1" in meta


def test_export_m4b_success(setup_mixed_files):
    """Test export process with mocked subprocess."""
    project_id = setup_mixed_files["id"]
    output_path = setup_mixed_files["dir"] / "07_EXPORT" / "audiobook" / "book.m4b"

    with patch("subprocess.run") as mock_run, patch(
        "audioformation.export.m4b.get_duration", return_value=60.0
    ):

        mock_run.return_value.returncode = 0

        result = export_project_m4b(project_id, output_path)

        assert result is True

        # Verify ffmpeg called
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-f" in cmd and "concat" in cmd
        assert str(output_path) in cmd
        assert "-map_metadata" in cmd


def test_export_no_files_fails(sample_project):
    """Export should fail gracefully if no mixed files found."""
    # Ensure mix dir is empty
    mix_dir = sample_project["dir"] / "06_MIX" / "renders"
    mix_dir.mkdir(parents=True, exist_ok=True)

    output_path = sample_project["dir"] / "out.m4b"

    result = export_project_m4b(sample_project["id"], output_path)
    assert result is False


def test_export_with_cover_art(setup_mixed_files):
    """Test export command structure when cover art exists."""
    project_id = setup_mixed_files["id"]
    output_path = setup_mixed_files["dir"] / "out.m4b"

    # Create dummy cover
    cover_path = setup_mixed_files["dir"] / "00_CONFIG" / "cover.jpg"
    cover_path.parent.mkdir(parents=True, exist_ok=True)
    cover_path.touch()

    # Update project.json to reference the cover art
    # The fixture creates project.json with cover_art: None
    pj_path = setup_mixed_files["dir"] / "project.json"
    pj = json.loads(pj_path.read_text(encoding="utf-8"))
    pj["export"]["cover_art"] = "00_CONFIG/cover.jpg"
    pj_path.write_text(json.dumps(pj), encoding="utf-8")

    with patch("subprocess.run") as mock_run, patch(
        "audioformation.export.m4b.get_duration", return_value=10.0
    ):

        mock_run.return_value.returncode = 0

        export_project_m4b(project_id, output_path)

        cmd = mock_run.call_args[0][0]
        # Check if cover input is added
        assert str(cover_path) in cmd
        # Check mapping logic
        assert "-disposition:v" in cmd
        assert "attached_pic" in cmd
