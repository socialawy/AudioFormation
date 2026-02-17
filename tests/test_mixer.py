"""Tests for AudioMixer, VAD ducking, and mix pipeline (Node 6)."""

import sys
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
import numpy as np

# Ensure we can import from src
from audioformation.audio.mixer import AudioMixer
from audioformation.mix import mix_project
from audioformation.project import load_pipeline_status

# ──────────────────────────────────────────────
# Mocks & Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def mock_pydub(monkeypatch):
    """Refine pydub mock for mixer specifics."""
    # The global conftest mock is good, but we need specific behaviors
    # for get_array_of_samples and duration

    class MockSegment:
        def __init__(self, duration_ms=1000, channels=1, frame_rate=24000):
            self.duration_ms = duration_ms
            self.channels = channels
            self.frame_rate = frame_rate
            self.dBFS = -20.0

        def __len__(self):
            return self.duration_ms

        def get_array_of_samples(self):
            # Return array.array style iterable
            import array

            # Generate fake samples
            return array.array(
                "h",
                [1000] * int(self.duration_ms * self.frame_rate / 1000) * self.channels,
            )

        def _spawn(self, data):
            # Return a new segment from processed data
            return MockSegment(self.duration_ms, self.channels, self.frame_rate)

        def overlay(self, other, position=0):
            return self  # Mock returns self for chaining

        def apply_gain(self, gain):
            return self

        def export(self, path, format=None):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"MIXED_AUDIO")

        def __getitem__(self, item):
            # Handle slicing [start:end]
            if isinstance(item, slice):
                start = item.start or 0
                stop = item.stop or self.duration_ms
                return MockSegment(stop - start, self.channels, self.frame_rate)
            return self

        def __mul__(self, other):
            # Handle looping: segment * N
            return MockSegment(self.duration_ms * other, self.channels, self.frame_rate)

    # Patch AudioSegment in the module
    with patch("audioformation.audio.mixer.AudioSegment") as MockClass:
        MockClass.from_file.side_effect = lambda p: MockSegment()
        yield MockClass


@pytest.fixture
def mock_torch():
    """Mock torch and hub for VAD."""
    with patch("audioformation.audio.mixer.torch") as mock_torch:
        # Setup hub.load to return (model, utils)
        mock_model = MagicMock()
        mock_utils = [MagicMock()]  # get_speech_timestamps

        # Mock get_speech_timestamps return value
        # Returns list of dicts {'start': sample_idx, 'end': sample_idx}
        mock_utils[0].return_value = [
            {"start": 24000, "end": 48000}  # 1s to 2s at 24khz
        ]

        mock_torch.hub.load.return_value = (mock_model, mock_utils)
        mock_torch.from_numpy.return_value = MagicMock()

        yield mock_torch


# ──────────────────────────────────────────────
# Unit Tests: AudioMixer
# ──────────────────────────────────────────────


class TestAudioMixer:
    def test_init_defaults(self):
        config = {"target_lufs": -14}
        mixer = AudioMixer(config)
        assert mixer.target_lufs == -14
        assert mixer.master_volume == 0.9
        assert mixer.method == "vad"  # Default from code

    def test_init_config_override(self):
        config = {"ducking": {"method": "energy", "attenuation_db": -6.0}}
        mixer = AudioMixer(config)
        assert mixer.method == "energy"
        assert mixer.attenuation_db == -6.0

    def test_ensure_vad_model_success(self, mock_torch):
        mixer = AudioMixer({})
        mixer._ensure_vad_model()
        assert mixer._vad_model is not None
        assert mixer._get_speech_timestamps is not None

    def test_ensure_vad_model_fallback(self):
        """If torch fails to load, fallback to energy."""
        with patch(
            "audioformation.audio.mixer.torch.hub.load",
            side_effect=Exception("Network error"),
        ):
            mixer = AudioMixer({})
            mixer._ensure_vad_model()
            assert mixer.method == "energy"
            assert mixer._vad_model is None

    def test_mix_chapter_no_music(self, mock_pydub, tmp_path):
        """If music path is None, just export voice."""
        mixer = AudioMixer({})
        voice_path = tmp_path / "voice.wav"
        out_path = tmp_path / "out.wav"

        voice_path.touch()

        # Should return True
        ok = mixer.mix_chapter(voice_path, None, out_path)
        assert ok is True
        assert out_path.exists()

    def test_mix_chapter_with_music(self, mock_pydub, mock_torch, tmp_path):
        """Full mix flow with music."""
        mixer = AudioMixer({})
        voice = tmp_path / "voice.wav"
        music = tmp_path / "music.wav"
        out = tmp_path / "mixed.wav"

        voice.touch()
        music.touch()

        ok = mixer.mix_chapter(voice, music, out)
        assert ok is True
        assert out.exists()

    def test_generate_envelope_vad(self, mock_pydub, mock_torch):
        """Test envelope creation logic with VAD."""
        mixer = AudioMixer({"ducking": {"attenuation_db": -20}})

        # 5 seconds voice
        voice_seg = mock_pydub.from_file("fake")
        voice_seg.duration_ms = 5000
        voice_seg.frame_rate = 24000

        # 5 seconds total duration
        total_ms = 5000

        env = mixer._generate_envelope(voice_seg, total_ms)

        assert isinstance(env, np.ndarray)
        assert len(env) == total_ms

        # VAD mock returns speech at 1s-2s (24000-48000 samples)
        # Ducking should be applied around 1000ms - 2000ms
        # Attenuation -20dB = 0.1

        # Check a point in speech region (approx 1500ms)
        # Note: Envelope generation includes smoothing, so exact value check needs tolerance
        # But it should be < 1.0
        assert env[1500] < 0.9

        # Check silence region (start)
        assert env[0] == 1.0

    def test_generate_envelope_energy(self, mock_pydub):
        """Test envelope creation logic with Energy fallback."""
        mixer = AudioMixer({"ducking": {"method": "energy"}})

        voice_seg = mock_pydub.from_file("fake")
        # Ensure slicing works on the mock

        # We need to mock _get_energy_timestamps specifically since slicing MockSegment returns self
        with patch.object(
            mixer, "_get_energy_timestamps", return_value=[{"start": 1000, "end": 2000}]
        ):
            env = mixer._generate_envelope(voice_seg, 5000)

            assert env[1500] < 1.0
            assert env[0] == 1.0


# ──────────────────────────────────────────────
# Integration Tests: Pipeline
# ──────────────────────────────────────────────


class TestMixPipeline:
    @pytest.fixture
    def setup_project(self, sample_project, tmp_path):
        """Setup processed audio and music for mixing."""
        proj_dir = sample_project["dir"]

        # Create processed chapters (input for mix)
        proc_dir = proj_dir / "03_GENERATED" / "processed"
        proc_dir.mkdir(parents=True, exist_ok=True)
        (proc_dir / "ch01.wav").touch()
        (proc_dir / "ch02.wav").touch()

        # Create generated music
        music_dir = proj_dir / "05_MUSIC" / "generated"
        music_dir.mkdir(parents=True, exist_ok=True)
        (music_dir / "ambient_pad.wav").touch()

        return sample_project

    def test_mix_project_success(self, setup_project, mock_pydub):
        """Running mix_project finds chapters and music, produces output."""
        pid = setup_project["id"]

        # Patch mixer to avoid real processing
        with patch("audioformation.mix.AudioMixer") as MockMixer:
            instance = MockMixer.return_value
            instance.mix_chapter.return_value = True

            result = mix_project(pid)

            assert result is True
            # Expect 2 calls (ch01, ch02)
            assert instance.mix_chapter.call_count == 2

            # Check pipeline status updated
            status = load_pipeline_status(pid)
            assert status["nodes"]["mix"]["status"] == "complete"

    def test_mix_project_specific_music(self, setup_project, mock_pydub):
        """Specifying --music uses that file."""
        pid = setup_project["id"]

        with patch("audioformation.mix.AudioMixer") as MockMixer:
            instance = MockMixer.return_value
            instance.mix_chapter.return_value = True

            mix_project(pid, music_file="ambient_pad.wav")

            # Verify the second arg (music_path) in call
            call_args = instance.mix_chapter.call_args
            music_arg = call_args[0][1]  # (voice, music, out)
            assert music_arg.name == "ambient_pad.wav"

    def test_mix_project_no_music_fallback(self, setup_project, mock_pydub):
        """If no music found, passes None to mixer."""
        pid = setup_project["id"]

        # Delete music
        music_dir = setup_project["dir"] / "05_MUSIC" / "generated"
        for f in music_dir.glob("*"):
            f.unlink()

        with patch("audioformation.mix.AudioMixer") as MockMixer:
            instance = MockMixer.return_value
            instance.mix_chapter.return_value = True

            mix_project(pid)

            call_args = instance.mix_chapter.call_args
            assert call_args[0][1] is None  # music_path is None

    def test_mix_fails_if_no_audio(self, sample_project):
        """Fails gracefully if no processed audio found."""
        # Setup without creating 03_GENERATED files
        result = mix_project(sample_project["id"])
        assert result is False
