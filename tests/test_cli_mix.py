"""Tests for the 'mix' CLI command."""

from click.testing import CliRunner
import pytest
from unittest.mock import patch, MagicMock

from audioformation.cli import main
from audioformation.pipeline import get_node_status


@pytest.fixture
def runner():
    return CliRunner()


def test_mix_command_success(runner, sample_project, isolate_projects):
    """Test successful mix execution via CLI."""
    with patch("audioformation.mix.mix_project") as mock_mix, patch(
        "audioformation.pipeline.can_proceed_to", return_value=(True, "OK")
    ):

        mock_mix.return_value = True

        result = runner.invoke(main, ["mix", sample_project["id"]])

        assert result.exit_code == 0
        assert "Starting mix" in result.output
        mock_mix.assert_called_once()

        # Verify arguments passed to internal function
        args = mock_mix.call_args
        assert args[0][0] == sample_project["id"]  # project_id
        assert args[0][1] is None  # music_file default


def test_mix_command_with_music(runner, sample_project, isolate_projects):
    """Test mix command with specific music file."""
    with patch("audioformation.mix.mix_project") as mock_mix, patch(
        "audioformation.pipeline.can_proceed_to", return_value=(True, "OK")
    ):

        mock_mix.return_value = True

        result = runner.invoke(
            main, ["mix", sample_project["id"], "--music", "bg_music.wav"]
        )

        assert result.exit_code == 0
        mock_mix.assert_called_once()
        assert mock_mix.call_args[0][1] == "bg_music.wav"


def test_mix_command_gate_fail(runner, sample_project, isolate_projects):
    """Test mix blocked by pipeline gate."""
    with patch("audioformation.mix.mix_project") as mock_mix, patch(
        "audioformation.pipeline.can_proceed_to",
        return_value=(False, "Previous step failed"),
    ):

        result = runner.invoke(main, ["mix", sample_project["id"]])

        assert result.exit_code != 0
        assert "Cannot start mixing" in result.output
        mock_mix.assert_not_called()


def test_mix_command_internal_fail(runner, sample_project, isolate_projects):
    """Test CLI handles internal mix failure."""
    with patch("audioformation.mix.mix_project") as mock_mix, patch(
        "audioformation.pipeline.can_proceed_to", return_value=(True, "OK")
    ):

        # Simulate mix failure
        mock_mix.return_value = False

        result = runner.invoke(main, ["mix", sample_project["id"]])

        assert result.exit_code != 0
