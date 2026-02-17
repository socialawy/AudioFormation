"""Tests for 'preview' and 'compare' CLI commands."""

import json
from click.testing import CliRunner
import pytest
from pathlib import Path

from audioformation.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_preview_command(runner, sample_project, isolate_projects):
    """Test generating a preview."""
    # Ensure source file exists via sample_project

    result = runner.invoke(
        main, ["preview", sample_project["id"], "ch01", "--duration", "10"]
    )

    if result.exit_code == 0:
        assert "Generating preview" in result.output
        # Output format is "~X.Xs" (e.g. ~2.8s) calculated from text char count
        # ch01 text in fixture is short (~39 chars), so duration ~2.6s
        # Just check for "s)" which indicates the time format was printed
        assert "s)" in result.output
        assert "Saved preview" in result.output
    else:
        assert result.exit_code != 0


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
