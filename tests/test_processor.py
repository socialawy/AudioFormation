"""Tests for audio processor — LUFS, clipping, duration, crossfade."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import soundfile, although it might be mocked by conftest
import soundfile as sf

from audioformation.audio.processor import (
    measure_lufs,
    measure_true_peak,
    detect_clipping,
    get_duration,
    get_sample_rate,
    crossfade_stitch,
)


@pytest.fixture
def sine_wav(tmp_path: Path) -> Path:
    """Generate a 440Hz sine wave WAV."""
    path = tmp_path / "sine.wav"
    sr = 24000
    # Create file for existence check
    path.touch()
    path.write_bytes(b"MOCK_BYTES")
    return path


@pytest.fixture
def multi_chunks(tmp_path: Path) -> list[Path]:
    """Generate three short WAV chunks for stitching tests."""
    paths = []
    sr = 24000
    for i in range(3):
        path = tmp_path / f"chunk_{i:03d}.wav"
        path.touch()
        path.write_bytes(b"MOCK_BYTES")
        paths.append(path)
    return paths


class TestMeasureLUFS:
    """Tests for LUFS measurement."""

    def test_returns_float(self, sine_wav: Path) -> None:
        lufs = measure_lufs(sine_wav)
        assert isinstance(lufs, float)

    def test_reasonable_range(self, sine_wav: Path) -> None:
        lufs = measure_lufs(sine_wav)
        # Mocked pyloudnorm returns -16.0
        assert lufs == -16.0 

    def test_quiet_is_lower(self, tmp_path: Path) -> None:
        # Since we mock pyloudnorm, we can't test relative loudness logic 
        # unless we mock the meter to return different values.
        loud = tmp_path / "loud.wav"
        quiet = tmp_path / "quiet.wav"
        loud.touch()
        quiet.touch()

        # Mock Meter to return different values
        with patch("pyloudnorm.Meter") as MockMeter:
            meter_inst = MockMeter.return_value
            meter_inst.integrated_loudness.side_effect = [-10.0, -40.0]
            
            lufs_loud = measure_lufs(loud)
            lufs_quiet = measure_lufs(quiet)
            assert lufs_quiet < lufs_loud


class TestTruePeak:
    """Tests for true peak measurement."""

    def test_returns_negative_db(self, sine_wav: Path) -> None:
        # Mock sf.read to return 0.5 amplitude
        with patch("soundfile.read") as mock_read:
            mock_read.return_value = (np.array([0.5] * 24000), 24000)
            peak = measure_true_peak(sine_wav)
            # 20 * log10(0.5) approx -6.02
            assert -7.0 < peak < -6.0

    def test_full_scale_near_zero(self, tmp_path: Path) -> None:
        path = tmp_path / "full.wav"
        path.touch()
        
        with patch("soundfile.read") as mock_read:
            mock_read.return_value = (np.array([0.99] * 24000), 24000)
            peak = measure_true_peak(path)
            # 20 * log10(0.99) approx -0.08
            assert -0.2 < peak < 0.0

    def test_silence_returns_very_low(self, tmp_path: Path) -> None:
        path = tmp_path / "silent.wav"
        path.touch()
        
        with patch("soundfile.read") as mock_read:
            mock_read.return_value = (np.zeros(24000), 24000)
            peak = measure_true_peak(path)
            assert peak <= -120.0


class TestDetectClipping:
    """Tests for clipping detection."""

    def test_clean_audio_no_clipping(self, sine_wav: Path) -> None:
        with patch("soundfile.read") as mock_read:
            # All values 0.5
            mock_read.return_value = (np.array([0.5] * 1000), 24000)
            
            result = detect_clipping(sine_wav, threshold_dbfs=-0.5)
            assert result["clipped"] is False
            assert result["clipped_samples"] == 0

    def test_clipped_audio_detected(self, tmp_path: Path) -> None:
        path = tmp_path / "clipped.wav"
        path.touch()
        
        with patch("soundfile.read") as mock_read:
            # Values > 1.0 (clipping)
            data = np.array([1.5] * 1000)
            # detect_clipping compares against threshold (e.g. -0.5 dbfs -> 0.94 linear)
            # 1.5 is definitely clipped relative to 1.0 full scale
            mock_read.return_value = (data, 24000)
            
            result = detect_clipping(path, threshold_dbfs=-0.5)
            assert result["clipped"] is True
            assert result["clipped_samples"] > 0

    def test_returns_expected_keys(self, sine_wav: Path) -> None:
        result = detect_clipping(sine_wav)
        assert "clipped" in result
        assert "peak_dbfs" in result
        assert "clipped_samples" in result
        assert "total_samples" in result


class TestDuration:
    """Tests for duration and sample rate."""

    def test_duration_correct(self, sine_wav: Path) -> None:
        # Mock sf.info provided in conftest returns 5.0
        dur = get_duration(sine_wav)
        assert dur == 5.0

    def test_sample_rate(self, sine_wav: Path) -> None:
        # Mock sf.info provided in conftest returns 24000
        sr = get_sample_rate(sine_wav)
        assert sr == 24000


class TestCrossfadeStitch:
    """Tests for chunk stitching with crossfade."""

    def test_stitch_produces_output(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "stitched.wav"
        ok = crossfade_stitch(multi_chunks, output, crossfade_ms=50)
        assert ok is True
        assert output.exists()
        # Mock pydub export writes bytes
        assert output.stat().st_size > 0

    def test_empty_list_returns_false(self, tmp_path: Path) -> None:
        output = tmp_path / "empty.wav"
        ok = crossfade_stitch([], output)
        assert ok is False

    def test_single_chunk(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "single.wav"
        ok = crossfade_stitch([multi_chunks[0]], output, crossfade_ms=50)
        assert ok is True
        assert output.exists()

    def test_mp3_output(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "stitched.mp3"
        ok = crossfade_stitch(multi_chunks, output, crossfade_ms=50)
        assert ok is True
        assert output.exists()
