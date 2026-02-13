"""Tests for audio processor — LUFS, clipping, duration, crossfade."""

import numpy as np
import soundfile as sf
import pytest
from pathlib import Path

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
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    sf.write(str(path), audio, sr)
    return path


@pytest.fixture
def multi_chunks(tmp_path: Path) -> list[Path]:
    """Generate three short WAV chunks for stitching tests."""
    paths = []
    sr = 24000
    for i in range(3):
        path = tmp_path / f"chunk_{i:03d}.wav"
        freq = 440 + (i * 100)
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        audio = 0.3 * np.sin(2 * np.pi * freq * t)
        sf.write(str(path), audio, sr)
        paths.append(path)
    return paths


class TestMeasureLUFS:
    """Tests for LUFS measurement."""

    def test_returns_float(self, sine_wav: Path) -> None:
        lufs = measure_lufs(sine_wav)
        assert isinstance(lufs, float)

    def test_reasonable_range(self, sine_wav: Path) -> None:
        lufs = measure_lufs(sine_wav)
        assert -30 < lufs < 0

    def test_quiet_is_lower(self, tmp_path: Path) -> None:
        sr = 24000
        t = np.linspace(0, 2.0, sr * 2, endpoint=False)

        loud = tmp_path / "loud.wav"
        sf.write(str(loud), 0.8 * np.sin(2 * np.pi * 440 * t), sr)

        quiet = tmp_path / "quiet.wav"
        sf.write(str(quiet), 0.01 * np.sin(2 * np.pi * 440 * t), sr)

        lufs_loud = measure_lufs(loud)
        lufs_quiet = measure_lufs(quiet)
        assert lufs_quiet < lufs_loud


class TestTruePeak:
    """Tests for true peak measurement."""

    def test_returns_negative_db(self, sine_wav: Path) -> None:
        peak = measure_true_peak(sine_wav)
        assert peak < 0  # 0.5 amplitude → ~-6 dBFS

    def test_full_scale_near_zero(self, tmp_path: Path) -> None:
        path = tmp_path / "full.wav"
        sr = 24000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        audio = 0.99 * np.sin(2 * np.pi * 440 * t)
        sf.write(str(path), audio, sr)

        peak = measure_true_peak(path)
        # 0.99 amplitude → ~-0.09 dBFS
        assert -1.0 < peak < 0.0

    def test_quiet_audio_low_peak(self, tmp_path: Path) -> None:
        path = tmp_path / "quiet.wav"
        sr = 24000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        audio = 0.01 * np.sin(2 * np.pi * 440 * t)
        sf.write(str(path), audio, sr)

        peak = measure_true_peak(path)
        assert peak < -30  # Very low peak

    def test_silence_returns_very_low(self, tmp_path: Path) -> None:
        path = tmp_path / "silent.wav"
        sr = 24000
        audio = np.zeros(sr)
        sf.write(str(path), audio, sr)

        peak = measure_true_peak(path)
        assert peak <= -120.0


class TestDetectClipping:
    """Tests for clipping detection."""

    def test_clean_audio_no_clipping(self, sine_wav: Path) -> None:
        result = detect_clipping(sine_wav, threshold_dbfs=-0.5)
        assert result["clipped"] is False
        assert result["clipped_samples"] == 0

    def test_clipped_audio_detected(self, tmp_path: Path) -> None:
        path = tmp_path / "clipped.wav"
        sr = 24000
        t = np.linspace(0, 1.0, sr, endpoint=False)
        audio = 1.5 * np.sin(2 * np.pi * 440 * t)
        audio = np.clip(audio, -1.0, 1.0)
        sf.write(str(path), audio, sr)

        result = detect_clipping(path, threshold_dbfs=-0.5)
        assert result["clipped"] is True
        assert result["clipped_samples"] > 0
        assert result["peak_dbfs"] >= -0.5

    def test_returns_expected_keys(self, sine_wav: Path) -> None:
        result = detect_clipping(sine_wav)
        assert "clipped" in result
        assert "peak_dbfs" in result
        assert "clipped_samples" in result
        assert "total_samples" in result


class TestDuration:
    """Tests for duration and sample rate."""

    def test_duration_correct(self, sine_wav: Path) -> None:
        dur = get_duration(sine_wav)
        assert abs(dur - 2.0) < 0.01  # 2 seconds ± tolerance

    def test_sample_rate(self, sine_wav: Path) -> None:
        sr = get_sample_rate(sine_wav)
        assert sr == 24000

    def test_short_file(self, tmp_path: Path) -> None:
        path = tmp_path / "short.wav"
        sr = 24000
        audio = np.zeros(int(sr * 0.1))  # 100ms
        sf.write(str(path), audio, sr)

        dur = get_duration(path)
        assert abs(dur - 0.1) < 0.01


class TestCrossfadeStitch:
    """Tests for chunk stitching with crossfade."""

    def test_stitch_produces_output(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "stitched.wav"
        ok = crossfade_stitch(multi_chunks, output, crossfade_ms=50)
        assert ok is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_stitched_longer_than_single(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        output = tmp_path / "stitched.wav"
        crossfade_stitch(multi_chunks, output, crossfade_ms=50)

        single_dur = get_duration(multi_chunks[0])
        stitched_dur = get_duration(output)
        # Stitched should be longer than any single chunk
        assert stitched_dur > single_dur

    def test_crossfade_shortens_total(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        # No crossfade
        out_no_fade = tmp_path / "no_fade.wav"
        crossfade_stitch(multi_chunks, out_no_fade, crossfade_ms=0, leading_silence_ms=0)

        # With crossfade
        out_fade = tmp_path / "fade.wav"
        crossfade_stitch(multi_chunks, out_fade, crossfade_ms=100, leading_silence_ms=0)

        dur_no_fade = get_duration(out_no_fade)
        dur_fade = get_duration(out_fade)

        # Crossfade overlaps audio, so result should be shorter
        assert dur_fade < dur_no_fade

    def test_leading_silence(self, multi_chunks: list[Path], tmp_path: Path) -> None:
        out_silence = tmp_path / "with_silence.wav"
        out_no_silence = tmp_path / "no_silence.wav"

        crossfade_stitch(multi_chunks, out_silence, crossfade_ms=50, leading_silence_ms=500)
        crossfade_stitch(multi_chunks, out_no_silence, crossfade_ms=50, leading_silence_ms=0)

        dur_s = get_duration(out_silence)
        dur_ns = get_duration(out_no_silence)

        # 500ms leading silence → ~0.5s longer
        assert abs((dur_s - dur_ns) - 0.5) < 0.05

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