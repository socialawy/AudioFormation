"""Tests for QC scanner — SNR, clipping, duration, LUFS checks."""

import numpy as np
import soundfile as sf
import pytest
from pathlib import Path

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
    path = tmp_path / "clean.wav"
    sr = 24000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # 440Hz sine at moderate amplitude
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)
    sf.write(str(path), audio, sr)
    return path


@pytest.fixture
def quiet_wav(tmp_path: Path) -> Path:
    """Generate a very quiet WAV."""
    path = tmp_path / "quiet.wav"
    sr = 24000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.001 * np.sin(2 * np.pi * 440 * t)
    sf.write(str(path), audio, sr)
    return path


@pytest.fixture
def clipped_wav(tmp_path: Path) -> Path:
    """Generate a clipped WAV."""
    path = tmp_path / "clipped.wav"
    sr = 24000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Over-driven sine that clips
    audio = 1.5 * np.sin(2 * np.pi * 440 * t)
    audio = np.clip(audio, -1.0, 1.0)
    sf.write(str(path), audio, sr)
    return path


@pytest.fixture
def silent_wav(tmp_path: Path) -> Path:
    """Generate a silent WAV."""
    path = tmp_path / "silent.wav"
    sr = 24000
    audio = np.zeros(sr * 2)  # 2 seconds of silence
    sf.write(str(path), audio, sr)
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
        result = scan_chunk(clean_wav, "test_001", default_qc_config, target_lufs=-16.0)
        # Clean audio should at minimum not fail critically
        assert result.status in ("pass", "warn")
        assert "snr" in result.checks
        assert "clipping" in result.checks
        assert "lufs" in result.checks

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
        result = _check_snr(clean_wav, min_db=10.0)
        assert result["status"] in ("pass", "warn")

    def test_silent_audio(self, silent_wav: Path) -> None:
        result = _check_snr(silent_wav, min_db=20.0)
        # Silent audio — can't measure SNR meaningfully
        assert result["status"] in ("warn", "fail")


class TestClippingCheck:
    """Tests for clipping detection."""

    def test_clean_audio_no_clipping(self, clean_wav: Path) -> None:
        result = _check_clipping(clean_wav, threshold_dbfs=-0.5)
        assert result["status"] == "pass"

    def test_clipped_audio_detected(self, clipped_wav: Path) -> None:
        result = _check_clipping(clipped_wav, threshold_dbfs=-0.5)
        assert result["status"] in ("warn", "fail")
        assert result["peak_dbfs"] >= -0.5

    def test_quiet_audio_no_clipping(self, quiet_wav: Path) -> None:
        result = _check_clipping(quiet_wav, threshold_dbfs=-0.5)
        assert result["status"] == "pass"


class TestDurationCheck:
    """Tests for duration sanity."""

    def test_matching_duration_passes(self, clean_wav: Path) -> None:
        result = _check_duration(clean_wav, expected=2.0, max_deviation_pct=30.0)
        assert result["status"] == "pass"

    def test_very_wrong_duration_fails(self, clean_wav: Path) -> None:
        # Expect 10 seconds but file is ~2 seconds
        result = _check_duration(clean_wav, expected=10.0, max_deviation_pct=30.0)
        assert result["status"] == "fail"

    def test_slightly_off_warns(self, clean_wav: Path) -> None:
        # Expect 1.4s, actual ~2s — about 40% off
        result = _check_duration(clean_wav, expected=1.4, max_deviation_pct=30.0)
        assert result["status"] in ("warn", "fail")


class TestLUFSCheck:
    """Tests for LUFS deviation."""

    def test_lufs_measurement(self, clean_wav: Path) -> None:
        result = _check_lufs(clean_wav, target=-16.0, max_deviation=10.0)
        # With a generous deviation, clean audio should pass
        assert result["status"] in ("pass", "warn")
        assert "lufs" in result

    def test_silent_audio_lufs(self, silent_wav: Path) -> None:
        # Silent audio has very low LUFS — should deviate significantly
        result = _check_lufs(silent_wav, target=-16.0, max_deviation=3.0)
        # pyloudnorm returns -inf for silence, so this should fail or warn
        assert result["status"] in ("warn", "fail")


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