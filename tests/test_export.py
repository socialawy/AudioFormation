"""Tests for audio export — MP3, WAV, manifest generation."""

import json
import numpy as np
import soundfile as sf
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audioformation.export.mp3 import export_mp3, export_wav, export_project_mp3
from audioformation.export.metadata import sha256_file, generate_manifest


@pytest.fixture
def sample_wav(tmp_path: Path) -> Path:
    """Generate a sample WAV file."""
    path = tmp_path / "sample.wav"
    sr = 24000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)
    # Using sf.write from conftest side_effect
    sf.write(str(path), audio, sr)
    return path


class TestMP3Export:
    """Tests for MP3 export."""

    def test_export_creates_file(self, sample_wav: Path, tmp_path: Path) -> None:
        output = tmp_path / "output.mp3"
        with patch("audioformation.export.mp3.AudioSegment") as MockAudioSegment:
            mock_segment = MagicMock()
            MockAudioSegment.from_file.return_value = mock_segment

            def _export(path, format=None, **kwargs):
                Path(path).write_bytes(b"mock mp3 data")
            mock_segment.export.side_effect = _export

            ok = export_mp3(sample_wav, output, bitrate=128)
            assert ok is True
            assert output.exists()
            assert output.stat().st_size > 0

    def test_export_project_mp3(self, sample_wav: Path, sample_project) -> None:
        """Test exporting full project as MP3."""
        # Setup mixed file
        mix_dir = sample_project["dir"] / "06_MIX"
        mix_dir.mkdir(parents=True, exist_ok=True)
        mixed_file = mix_dir / f"{sample_project['id']}_mixed.wav"
        # Copy sample wav to mixed file
        mixed_file.write_bytes(sample_wav.read_bytes())

        with patch("audioformation.export.mp3.AudioSegment") as MockAudioSegment:
            mock_segment = MagicMock()
            MockAudioSegment.from_file.return_value = mock_segment
            def _export(path, format=None, **kwargs):
                Path(path).write_bytes(b"mock mp3 data")
            mock_segment.export.side_effect = _export

            ok = export_project_mp3(sample_project["id"])
            assert ok is True

            export_dir = sample_project["dir"] / "07_EXPORT" / "audiobook"
            assert (export_dir / f"{sample_project['id']}.mp3").exists()

    def test_export_with_different_bitrates(
        self, sample_wav: Path, tmp_path: Path
    ) -> None:
        """Verify higher bitrate produces larger file (simulated)."""
        out_128 = tmp_path / "out_128.mp3"
        out_320 = tmp_path / "out_320.mp3"

        # Use patch to temporarily override the export behavior
        with patch("audioformation.export.mp3.AudioSegment") as MockAudioSegment:
            # Create a fresh mock instance for this specific test
            test_segment = MagicMock()

            # Mock export to modify file size based on bitrate arg
            def _export_side_effect(path, format=None, bitrate=None, **kwargs):
                p = Path(path)
                # In export_mp3 it's passed as bitrate="128k" (string)
                val = bitrate

                # Parse "128k" -> 128
                if isinstance(val, str):
                    val = val.lower().replace("k", "")

                try:
                    kbps = int(val)
                except (ValueError, TypeError):
                    kbps = 128

                # Write fake bytes proportional to bitrate
                # 128 -> 1280 bytes, 320 -> 3200 bytes
                p.write_bytes(b"0" * kbps * 10)

            test_segment.export.side_effect = _export_side_effect

            # Override from_file to return our custom test_segment
            def _from_file_override(path, **kwargs):
                if not Path(path).exists():
                    raise FileNotFoundError(f"File not found: {path}")
                return test_segment

            MockAudioSegment.from_file.side_effect = _from_file_override

            export_mp3(sample_wav, out_128, bitrate=128)
            export_mp3(sample_wav, out_320, bitrate=320)

            # Check that different bitrates resulted in different (simulated) file sizes
            assert out_320.exists()
            assert out_128.exists()
            assert out_320.stat().st_size > out_128.stat().st_size

    def test_export_nonexistent_source_returns_false(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent.wav"
        output = tmp_path / "output.mp3"
        # conftest mock is configured to raise FileNotFoundError for missing inputs
        ok = export_mp3(fake, output)
        assert ok is False


class TestWAVExport:
    """Tests for WAV export (copy/convert)."""

    def test_export_creates_file(self, sample_wav: Path, tmp_path: Path) -> None:
        output = tmp_path / "output.wav"
        ok = export_wav(sample_wav, output)
        assert ok is True
        assert output.exists()
        assert output.stat().st_size > 0


class TestSHA256:
    """Tests for file checksums."""

    def test_sha256_deterministic(self, sample_wav: Path) -> None:
        hash1 = sha256_file(sample_wav)
        hash2 = sha256_file(sample_wav)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_different_files_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert sha256_file(f1) != sha256_file(f2)


class TestManifest:
    """Tests for manifest generation."""

    def test_generates_manifest(self, sample_wav: Path, tmp_path: Path) -> None:
        # Setup export dir with a file
        export_dir = tmp_path / "export"
        export_dir.mkdir()

        output = export_dir / "chapter01.mp3"

        with patch("audioformation.export.mp3.AudioSegment") as MockAudioSegment:
            mock_segment = MagicMock()
            MockAudioSegment.from_file.return_value = mock_segment
            def _export(path, format=None, **kwargs):
                Path(path).write_bytes(b"mock mp3 data")
            mock_segment.export.side_effect = _export

            export_mp3(sample_wav, output)

        manifest_path = generate_manifest(
            export_dir,
            "TEST_PROJECT",
            metadata={"author": "Test Author"},
        )

        assert manifest_path.exists()

        data = json.loads(manifest_path.read_text())
        assert data["project_id"] == "TEST_PROJECT"
        assert data["total_files"] == 1
        assert data["metadata"]["author"] == "Test Author"
        assert data["files"][0]["sha256"]
        assert data["files"][0]["size_bytes"] > 0

    def test_manifest_excludes_itself(self, tmp_path: Path) -> None:
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        (export_dir / "test.txt").write_text("data")

        # Generate manifest twice — should not include itself
        generate_manifest(export_dir, "TEST")
        manifest_path = generate_manifest(export_dir, "TEST")

        data = json.loads(manifest_path.read_text())
        filenames = [f["path"] for f in data["files"]]
        assert "manifest.json" not in filenames

    def test_manifest_walks_subdirs(self, tmp_path: Path) -> None:
        export_dir = tmp_path / "export"
        sub = export_dir / "chapters"
        sub.mkdir(parents=True)
        (sub / "ch01.mp3").write_bytes(b"fake mp3")
        (sub / "ch02.mp3").write_bytes(b"fake mp3 2")

        manifest_path = generate_manifest(export_dir, "TEST")
        data = json.loads(manifest_path.read_text())
        assert data["total_files"] == 2
