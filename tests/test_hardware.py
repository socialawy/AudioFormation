"""Tests for hardware detection utilities."""

import pytest
from unittest.mock import patch, MagicMock
from audioformation.utils.hardware import detect_gpu, detect_ffmpeg, detect_all, write_hardware_json

import sys

class TestHardwareDetection:

    def test_detect_gpu_torch(self):
        """Test GPU detection via PyTorch."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "Test GPU"

        props = MagicMock()
        props.total_memory = 8 * 1024**3
        mock_torch.cuda.get_device_properties.return_value = props
        mock_torch.cuda.memory_reserved.return_value = 1 * 1024**3
        mock_torch.version.cuda = "11.8"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            # Must reload or ensuring detect_gpu imports it fresh?
            # detect_gpu imports inside function: "import torch"
            # So patch.dict should work.
            result = detect_gpu()

        assert result["gpu_available"] is True
        assert result["gpu_name"] == "Test GPU"
        assert result["vram_total_gb"] == 8.0
        assert result["vram_free_gb"] == 7.0
        assert result["cuda_available"] is True
        assert result["recommended_vram_strategy"] == "empty_cache_per_chapter"

    @patch("subprocess.run")
    def test_detect_gpu_nvidia_smi(self, mock_run):
        """Test GPU detection via nvidia-smi fallback."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        # name, total, free (in MiB)
        mock_proc.stdout = "NVIDIA T4, 15109, 10000"
        mock_run.return_value = mock_proc

        # Ensure torch import fails
        with patch.dict(sys.modules, {"torch": None}):
            result = detect_gpu()

        assert result["gpu_available"] is True
        assert result["gpu_name"] == "NVIDIA T4"
        assert result["vram_total_gb"] > 14.0
        assert result["cuda_available"] is True

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_detect_gpu_none(self, mock_run):
        """Test no GPU detected."""
        with patch.dict(sys.modules, {"torch": None}):
            result = detect_gpu()
        assert result["gpu_available"] is False
        assert result["recommended_vram_strategy"] == "cpu_only"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_detect_ffmpeg_found(self, mock_run, mock_which):
        """Test ffmpeg detection success."""
        mock_which.return_value = "/usr/bin/ffmpeg"

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright (c) 2000-2021 the FFmpeg developers\n..."
        mock_run.return_value = mock_proc

        result = detect_ffmpeg()

        assert result["ffmpeg_available"] is True
        assert result["ffmpeg_path"] == "/usr/bin/ffmpeg"
        assert "4.4.2" in result["ffmpeg_version"]

    @patch("shutil.which")
    def test_detect_ffmpeg_not_found(self, mock_which):
        """Test ffmpeg detection failure."""
        mock_which.return_value = None

        result = detect_ffmpeg()

        assert result["ffmpeg_available"] is False
        assert result["ffmpeg_path"] is None

    @patch("audioformation.utils.hardware.detect_gpu")
    @patch("audioformation.utils.hardware.detect_ffmpeg")
    def test_detect_all(self, mock_ffmpeg, mock_gpu):
        """Test detect_all combines results."""
        mock_gpu.return_value = {"gpu": True}
        mock_ffmpeg.return_value = {"ffmpeg": True}

        result = detect_all()
        assert result["gpu"] is True
        assert result["ffmpeg"] is True

    @patch("audioformation.utils.hardware.detect_all")
    def test_write_hardware_json(self, mock_detect, tmp_path):
        """Test writing hardware.json."""
        mock_detect.return_value = {"gpu": True}

        project_dir = tmp_path / "TEST_PROJECT"
        config_dir = project_dir / "00_CONFIG"
        config_dir.mkdir(parents=True)

        write_hardware_json(project_dir)

        hw_file = config_dir / "hardware.json"
        assert hw_file.exists()
        assert '"gpu": true' in hw_file.read_text()
