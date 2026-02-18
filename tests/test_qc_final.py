"""Tests for QC Final (Node 7) — validating mixed audio."""

import pytest
from unittest.mock import patch

from audioformation.qc.final import scan_final_mix
from audioformation.pipeline import get_node_status


class TestQCFinalScanner:
    @pytest.fixture
    def mock_processor(self):
        """Mock audio measurement functions."""
        with (
            patch("audioformation.qc.final.measure_lufs") as m_lufs,
            patch("audioformation.qc.final.measure_true_peak") as m_tp,
            patch("audioformation.qc.final.detect_clipping") as m_clip,
            patch("audioformation.qc.final.get_duration") as m_dur,
        ):
            yield {"lufs": m_lufs, "tp": m_tp, "clip": m_clip, "dur": m_dur}

    @pytest.fixture
    def setup_mix_dir(self, sample_project):
        """Create mock mix directory with a wav file."""
        mix_dir = sample_project["dir"] / "06_MIX" / "renders"
        mix_dir.mkdir(parents=True, exist_ok=True)
        wav = mix_dir / "ch01.wav"
        wav.touch()
        return wav

    def test_passing_audio(self, sample_project, setup_mix_dir, mock_processor):
        """Test audio that meets all criteria."""
        # Setup: Target -16, Limit -1.0
        # Mock: -16.5 LUFS, -2.0 TP, No clipping

        mock_processor["lufs"].return_value = -16.5
        mock_processor["tp"].return_value = -2.0
        mock_processor["clip"].return_value = {"clipped": False}
        mock_processor["dur"].return_value = 60.0

        report = scan_final_mix(sample_project["id"])

        assert report.passed is True
        assert report.passed_files == 1
        assert report.results[0].status == "pass"

        # Verify node status updated
        status = get_node_status(sample_project["id"], "qc_final")
        assert status["status"] == "complete"

    def test_lufs_fail(self, sample_project, setup_mix_dir, mock_processor):
        """Test audio with bad LUFS (too loud)."""
        # Target -16, measured -14.0 (diff 2.0 > 1.0 tolerance)
        mock_processor["lufs"].return_value = -14.0
        mock_processor["tp"].return_value = -2.0
        mock_processor["clip"].return_value = {"clipped": False}
        mock_processor["dur"].return_value = 60.0

        report = scan_final_mix(sample_project["id"])

        assert report.passed is False
        assert report.failed_files == 1
        assert report.results[0].status == "fail"
        assert any("LUFS" in m for m in report.results[0].messages)

    def test_true_peak_fail(self, sample_project, setup_mix_dir, mock_processor):
        """Test audio exceeding True Peak limit."""
        # Limit -1.0, measured -0.5
        mock_processor["lufs"].return_value = -16.0
        mock_processor["tp"].return_value = -0.5
        mock_processor["clip"].return_value = {"clipped": False}
        mock_processor["dur"].return_value = 60.0

        report = scan_final_mix(sample_project["id"])

        assert report.passed is False
        assert any("True Peak" in m for m in report.results[0].messages)

    def test_clipping_fail(self, sample_project, setup_mix_dir, mock_processor):
        """Test audio with clipping detected."""
        mock_processor["lufs"].return_value = -16.0
        mock_processor["tp"].return_value = -2.0
        mock_processor["clip"].return_value = {"clipped": True}
        mock_processor["dur"].return_value = 60.0

        report = scan_final_mix(sample_project["id"])

        assert report.passed is False
        assert any("clipping" in m.lower() for m in report.results[0].messages)

    def test_no_files_fails(self, sample_project):
        """Empty mix directory results in no report but failed status?"""
        # Ensure dir exists but empty
        mix_dir = sample_project["dir"] / "06_MIX" / "renders"
        mix_dir.mkdir(parents=True, exist_ok=True)

        report = scan_final_mix(sample_project["id"])

        # Should likely fail the node because nothing to check
        status = get_node_status(sample_project["id"], "qc_final")
        assert status["status"] == "failed"
        assert report.total_files == 0

    def test_measurement_exception_handled(
        self, sample_project, setup_mix_dir, mock_processor
    ):
        """Scanner handles exceptions during file reading."""
        mock_processor["lufs"].side_effect = ValueError("Corrupt file")

        report = scan_final_mix(sample_project["id"])

        assert report.passed is False
        assert report.results[0].status == "fail"
        assert "Measurement error" in report.results[0].messages[0]
