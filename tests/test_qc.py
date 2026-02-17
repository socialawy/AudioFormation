"""Tests for QC scanner — SNR, clipping, duration, LUFS checks."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch

from audioformation.qc.scanner import (
    scan_chunk,
    QCReport,
    ChunkQCResult,
    _check_snr,
    _check_clipping,
    _check_duration,
    _check_lufs,
)


@pytest.fixture
def clean_wav(tmp_path: Path) -> Path:
    """Generate a clean sine wave WAV for testing."""
    import numpy as np
    import soundfile as sf

    path = tmp_path / "clean.wav"
    sr = 24000
    duration = 2.0  # 2 seconds
    t = np.linspace(0, duration, int(sr * duration), False)
    # Generate clean 440Hz sine wave at moderate volume
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    sf.write(str(path), tone, sr)
    return path


@pytest.fixture
def default_qc_config() -> dict:
    """Default QC configuration."""
    return {
        "snr_min_db": 20.0,
        "max_duration_deviation_percent": 30.0,
        "clipping_threshold_dbfs": -0.5,
        "lufs_deviation_max": 3.0,
        "pitch_jump_max_semitones": 12.0,
        "boundary_artifact_check": True,
    }


class TestScanChunk:
    """Tests for the full chunk scanner."""

    def test_clean_audio_passes(self, clean_wav: Path, default_qc_config: dict) -> None:
        # Mock sub-checks to pass
        with patch("audioformation.qc.scanner._check_snr") as m_snr, patch(
            "audioformation.qc.scanner._check_clipping"
        ) as m_clip, patch("audioformation.qc.scanner._check_lufs") as m_lufs:

            m_snr.return_value = {"status": "pass"}
            m_clip.return_value = {"status": "pass"}
            m_lufs.return_value = {"status": "pass"}

            result = scan_chunk(
                clean_wav, "test_001", default_qc_config, target_lufs=-16.0
            )
            assert result.status == "pass"
            assert "snr" in result.checks

    def test_missing_file_fails(self, tmp_path: Path, default_qc_config: dict) -> None:
        fake_path = tmp_path / "nonexistent.wav"
        result = scan_chunk(fake_path, "test_missing", default_qc_config)
        assert result.status == "fail"
        assert result.checks["file_exists"]["status"] == "fail"

    def test_chunk_id_preserved(self, clean_wav: Path, default_qc_config: dict) -> None:
        result = scan_chunk(clean_wav, "ch01_005", default_qc_config)
        assert result.chunk_id == "ch01_005"


class TestSNRCheck:
    """Tests for SNR estimation."""

    def test_clean_audio_good_snr(self, clean_wav: Path) -> None:
        # Simulate high energy speech and low energy noise
        # 1.0 vs 0.01 -> 20 * log10(100) = 40dB
        data = np.concatenate([np.full(1000, 0.01), np.full(1000, 1.0)])

        with patch("soundfile.read") as mock_read:
            mock_read.return_value = (data, 24000)

            result = _check_snr(clean_wav, min_db=20.0)
            assert result["status"] == "pass"
            assert result["snr_db"] > 30.0

    def test_silent_audio(self, clean_wav: Path) -> None:
        # Silence/Low energy -> Warn or Fail
        data = np.zeros(2000)
        with patch("soundfile.read") as mock_read:
            mock_read.return_value = (data, 24000)
            result = _check_snr(clean_wav, min_db=20.0)
            # Should be warn because "No energy detected"
            assert result["status"] in ("warn", "fail")


class TestClippingCheck:
    """Tests for clipping detection."""

    def test_clean_audio_no_clipping(self, clean_wav: Path) -> None:
        with patch("soundfile.read") as mock_read:
            mock_read.return_value = (np.array([0.5] * 1000), 24000)
            result = _check_clipping(clean_wav, threshold_dbfs=-0.5)
            assert result["status"] == "pass"

    def test_clipped_audio_detected(self, clean_wav: Path) -> None:
        with patch("soundfile.read") as mock_read:
            # 1.5 exceeds typical clipping threshold
            mock_read.return_value = (np.array([1.5] * 1000), 24000)
            result = _check_clipping(clean_wav, threshold_dbfs=-0.5)
            assert result["status"] in ("warn", "fail")


class TestDurationCheck:
    """Tests for duration sanity."""

    def test_matching_duration_passes(self, clean_wav: Path) -> None:
        with patch("audioformation.qc.scanner.get_duration") as mock_dur:
            mock_dur.return_value = 2.0
            result = _check_duration(clean_wav, expected=2.0, max_deviation_pct=30.0)
            assert result["status"] == "pass"

    def test_very_wrong_duration_fails(self, clean_wav: Path) -> None:
        with patch("audioformation.qc.scanner.get_duration") as mock_dur:
            mock_dur.return_value = 2.0
            # Expected 10, got 2 -> 80% deviation
            result = _check_duration(clean_wav, expected=10.0, max_deviation_pct=30.0)
            assert result["status"] == "fail"


class TestLUFSCheck:
    """Tests for LUFS deviation."""

    def test_lufs_measurement(self, clean_wav: Path) -> None:
        with patch("audioformation.qc.scanner.measure_lufs") as mock_lufs:
            mock_lufs.return_value = -16.0
            result = _check_lufs(clean_wav, target=-16.0, max_deviation=3.0)
            assert result["status"] == "pass"

    def test_lufs_fail(self, clean_wav: Path) -> None:
        with patch("audioformation.qc.scanner.measure_lufs") as mock_lufs:
            mock_lufs.return_value = -25.0
            # Target -16, Actual -25 -> diff 9. Max deviation 3.
            result = _check_lufs(clean_wav, target=-16.0, max_deviation=3.0)
            assert result["status"] == "fail"


class TestQCReport:
    """Tests for QC report data structure."""

    def test_empty_report(self) -> None:
        report = QCReport(project_id="TEST")
        assert report.pass_count == 0
        assert report.fail_count == 0
        assert report.fail_rate == 0.0

    def test_report_counts(self) -> None:
        report = QCReport(project_id="TEST")

        pass_chunk = ChunkQCResult(chunk_id="c1", file="c1.wav")
        pass_chunk.checks["snr"] = {"status": "pass"}
        report.chunks.append(pass_chunk)

        fail_chunk = ChunkQCResult(chunk_id="c2", file="c2.wav")
        fail_chunk.checks["snr"] = {"status": "fail", "message": "Low SNR"}
        report.chunks.append(fail_chunk)

        warn_chunk = ChunkQCResult(chunk_id="c3", file="c3.wav")
        warn_chunk.checks["snr"] = {"status": "warn", "message": "Marginal"}
        report.chunks.append(warn_chunk)

        assert report.pass_count == 1
        assert report.fail_count == 1
        assert report.warn_count == 1
        assert report.fail_rate == pytest.approx(33.33, abs=0.1)

    def test_report_serialization(self, tmp_path: Path) -> None:
        report = QCReport(project_id="TEST", chapter_id="ch01")

        chunk = ChunkQCResult(chunk_id="c1", file="c1.wav")
        chunk.checks["snr"] = {"status": "pass", "snr_db": 25.3}
        report.chunks.append(chunk)

        output = tmp_path / "qc_report.json"
        report.save(output)

        assert output.exists()

        import json

        data = json.loads(output.read_text())
        assert data["project_id"] == "TEST"
        assert data["chapter_id"] == "ch01"
        assert data["total_chunks"] == 1
        assert data["passed"] == 1
