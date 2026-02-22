"""Tests for 'preview' and 'compare' CLI commands."""

from click.testing import CliRunner
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from audioformation.cli import main
from audioformation.engines.base import GenerationResult


@pytest.fixture
def runner():
    return CliRunner()


def test_preview_command(runner, sample_project, isolate_projects):
    """Test generating a preview."""
    # Ensure source file exists via sample_project

    # Mock EdgeTTSEngine.generate to avoid network/ffmpeg
    with patch("audioformation.engines.edge_tts.EdgeTTSEngine.generate") as mock_gen:
        mock_gen.return_value = GenerationResult(
            success=True,
            output_path=Path("dummy.wav"),
            duration_sec=2.5,
            sample_rate=24000
        )

        result = runner.invoke(
            main, ["preview", sample_project["id"], "ch01", "--duration", "10"]
        )

        if result.exit_code == 0:
            assert "Generating preview" in result.output
            assert "Saved preview" in result.output
        else:
            print(result.output)
            assert result.exit_code == 0


def test_compare_command(runner, sample_project, isolate_projects):
    """Test generating comparisons."""
    result = runner.invoke(
        main, ["compare", sample_project["id"], "ch01", "--engines", "edge,gtts"]
    )

    assert "Comparing engines" in result.output
    assert "edge" in result.output
    assert "gtts" in result.output


def test_preview_invalid_chapter(runner, sample_project, isolate_projects):
    result = runner.invoke(
        main, ["preview", sample_project["id"], "nonexistent_chapter"]
    )
    assert result.exit_code != 0
    assert "not found" in result.output
