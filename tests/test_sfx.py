"""Tests for FXForge (SFX generation)."""

import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

from audioformation.audio.sfx import generate_sfx
from audioformation.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def mock_write_side_effect(file, data, samplerate, **kwargs):
    """Simulate writing file."""
    Path(file).parent.mkdir(parents=True, exist_ok=True)
    Path(file).touch()


def test_generate_sfx_whoosh(tmp_path):
    """Test whoosh generation."""
    out = tmp_path / "whoosh.wav"
    with patch("soundfile.write", side_effect=mock_write_side_effect):
        data = generate_sfx("whoosh", output_path=out, duration=1.0)
        assert len(data) == 44100
        assert out.exists()


def test_generate_sfx_impact(tmp_path):
    """Test impact generation."""
    out = tmp_path / "impact.wav"
    with patch("soundfile.write", side_effect=mock_write_side_effect):
        data = generate_sfx("impact", output_path=out, duration=1.0)
        assert len(data) == 44100
        assert out.exists()


def test_generate_sfx_ui_click(tmp_path):
    """Test ui_click generation (fixed duration)."""
    out = tmp_path / "click.wav"
    with patch("soundfile.write", side_effect=mock_write_side_effect):
        data = generate_sfx(
            "ui_click", output_path=out, duration=5.0
        )  # Should ignore 5.0
        # Fixed duration is 0.1s in sfx.py
        assert len(data) == 4410
        assert out.exists()


def test_generate_sfx_unknown_type():
    """Test invalid type raises error."""
    with pytest.raises(ValueError, match="Unknown SFX type"):
        generate_sfx("fake_type")


def test_cli_sfx_generate(runner, sample_project, isolate_projects):
    """Test CLI command."""
    with patch("soundfile.write", side_effect=mock_write_side_effect):
        result = runner.invoke(
            main,
            [
                "sfx",
                "generate",
                sample_project["id"],
                "--type",
                "whoosh",
                "--duration",
                "2.0",
            ],
        )

        assert result.exit_code == 0
        assert "Generated whoosh" in result.output

        # Verify file in 04_SFX/procedural
        sfx_dir = sample_project["dir"] / "04_SFX" / "procedural"
        assert len(list(sfx_dir.glob("*.wav"))) == 1
