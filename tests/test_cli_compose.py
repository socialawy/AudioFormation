"""Tests for the 'compose' CLI command."""

from click.testing import CliRunner
import pytest
from pathlib import Path
from unittest.mock import patch

from audioformation.cli import main
from audioformation.pipeline import get_node_status

@pytest.fixture
def runner():
    return CliRunner()

def mock_generate_pad_side_effect(*args, **kwargs):
    """Simulate file creation since dependencies might be mocked."""
    output_path = kwargs.get("output_path")
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).touch()

def test_compose_default(runner, sample_project, isolate_projects):
    """Test compose with default settings."""
    with patch("audioformation.audio.composer.generate_pad") as mock_gen:
        mock_gen.side_effect = mock_generate_pad_side_effect
        
        result = runner.invoke(main, ["compose", sample_project["id"]])
        
        assert result.exit_code == 0
        assert "Generating ambient pad" in result.output
        assert "contemplative" in result.output
        assert "60.0s" in result.output  # Fixed: matches float formatting
        
        # Check file created
        music_dir = sample_project["dir"] / "05_MUSIC" / "generated"
        wavs = list(music_dir.glob("*.wav"))
        assert len(wavs) == 1
        assert "contemplative" in wavs[0].name

        # Check pipeline status
        status = get_node_status(sample_project["id"], "compose")
        assert status["status"] == "complete"

def test_compose_custom_params(runner, sample_project, isolate_projects):
    """Test compose with custom preset and duration."""
    with patch("audioformation.audio.composer.generate_pad") as mock_gen:
        mock_gen.side_effect = mock_generate_pad_side_effect

        result = runner.invoke(main, [
            "compose", sample_project["id"],
            "--preset", "tense",
            "--duration", "10"
        ])
        
        assert result.exit_code == 0
        assert "tense" in result.output
        assert "10.0s" in result.output

        music_dir = sample_project["dir"] / "05_MUSIC" / "generated"
        wavs = list(music_dir.glob("*.wav"))
        tense_wavs = [f for f in wavs if "tense" in f.name]
        assert len(tense_wavs) == 1

def test_compose_list_presets(runner, sample_project, isolate_projects):
    """Test listing available presets."""
    result = runner.invoke(main, ["compose", sample_project["id"], "--list"])
    
    assert result.exit_code == 0
    assert "Available presets:" in result.output
    assert "contemplative" in result.output
    assert "tense" in result.output
    # Should not generate anything
    assert "Generating" not in result.output

def test_compose_invalid_preset(runner, sample_project, isolate_projects):
    """Test error on invalid preset."""
    result = runner.invoke(main, [
        "compose", sample_project["id"],
        "--preset", "invalid_mood"
    ])
    
    assert result.exit_code != 0
    assert "Unknown preset" in result.output

def test_compose_custom_output(runner, sample_project, isolate_projects):
    """Test specifying output filename."""
    with patch("audioformation.audio.composer.generate_pad") as mock_gen:
        mock_gen.side_effect = mock_generate_pad_side_effect

        result = runner.invoke(main, [
            "compose", sample_project["id"],
            "--output", "my_custom_pad.wav",
            "--duration", "5"
        ])
        
        assert result.exit_code == 0
        music_dir = sample_project["dir"] / "05_MUSIC" / "generated"
        assert (music_dir / "my_custom_pad.wav").exists()
