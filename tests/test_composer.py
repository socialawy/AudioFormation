"""Tests for the ambient pad generator (ComposeEngine Tier 1)."""

import numpy as np
import pytest

from audioformation.audio.composer import (
    generate_pad,
    list_presets,
    get_preset,
    PadPreset,
)
from audioformation.audio.synthesis import (
    oscillator,
    cents_to_ratio,
    generate_noise,
    apply_envelope,
)


class TestPresets:
    """Tests for preset management."""

    def test_list_presets_not_empty(self) -> None:
        presets = list_presets()
        assert len(presets) >= 5
        assert "contemplative" in presets
        assert "tense" in presets
        assert "wonder" in presets
        assert "melancholy" in presets
        assert "triumph" in presets

    def test_get_preset_returns_padpreset(self) -> None:
        p = get_preset("contemplative")
        assert isinstance(p, PadPreset)
        assert p.name == "contemplative"
        assert p.base_freq > 0

    def test_get_unknown_preset_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset("nonexistent")

    def test_silence_preset_is_silent(self) -> None:
        p = get_preset("silence")
        assert p.base_amplitude == 0.0
        assert p.noise_amplitude == 0.0


class TestOscillators:
    """Tests for waveform generation."""

    def test_sine_output_shape(self) -> None:
        sig = oscillator(440.0, 1.0, 44100, "sine")
        assert sig.shape == (44100,)

    def test_sine_range(self) -> None:
        sig = oscillator(440.0, 1.0, 44100, "sine")
        assert np.max(sig) <= 1.0001
        assert np.min(sig) >= -1.0001

    def test_triangle_range(self) -> None:
        sig = oscillator(440.0, 1.0, 44100, "triangle")
        assert np.max(sig) <= 1.01
        assert np.min(sig) >= -1.01

    def test_saw_range(self) -> None:
        sig = oscillator(440.0, 1.0, 44100, "saw")
        assert np.max(sig) <= 1.01
        assert np.min(sig) >= -1.01

    def test_unknown_type_defaults_to_sine(self) -> None:
        sig = oscillator(440.0, 0.1, 44100, "unknown")
        sine = oscillator(440.0, 0.1, 44100, "sine")
        np.testing.assert_array_almost_equal(sig, sine)

    def test_cents_to_ratio(self) -> None:
        assert cents_to_ratio(0) == pytest.approx(1.0)
        assert cents_to_ratio(1200) == pytest.approx(2.0)
        assert cents_to_ratio(-1200) == pytest.approx(0.5)


class TestNoise:
    """Tests for noise generators."""

    def test_white_noise_shape(self) -> None:
        rng = np.random.default_rng(42)
        noise = generate_noise(44100, "white", rng)
        assert noise.shape == (44100,)

    def test_pink_noise_shape(self) -> None:
        rng = np.random.default_rng(42)
        noise = generate_noise(44100, "pink", rng)
        assert noise.shape == (44100,)

    def test_brown_noise_shape(self) -> None:
        rng = np.random.default_rng(42)
        noise = generate_noise(44100, "brown", rng)
        assert noise.shape == (44100,)

    def test_noise_is_normalized(self) -> None:
        rng = np.random.default_rng(42)
        for color in ["white", "pink", "brown"]:
            noise = generate_noise(44100, color, rng)
            assert np.max(np.abs(noise)) <= 1.01


class TestEnvelope:
    """Tests for fade-in/fade-out."""

    def test_fade_in_starts_at_zero(self) -> None:
        sig = np.ones(44100)
        result = apply_envelope(sig, 44100, fade_in_sec=1.0, fade_out_sec=0.0)
        assert result[0] == pytest.approx(0.0, abs=0.001)

    def test_fade_out_ends_at_zero(self) -> None:
        sig = np.ones(44100)
        result = apply_envelope(sig, 44100, fade_in_sec=0.0, fade_out_sec=1.0)
        assert result[-1] == pytest.approx(0.0, abs=0.001)

    def test_middle_is_unaffected(self) -> None:
        sig = np.ones(44100 * 10)  # 10 seconds
        result = apply_envelope(sig, 44100, fade_in_sec=1.0, fade_out_sec=1.0)
        # Middle should be ~1.0
        mid = len(result) // 2
        assert result[mid] == pytest.approx(1.0, abs=0.001)


class TestGeneratePad:
    """Tests for full pad generation."""

    def test_generates_array(self) -> None:
        audio = generate_pad("contemplative", duration_sec=2.0)
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32

    def test_correct_duration(self) -> None:
        audio = generate_pad("contemplative", duration_sec=3.0)
        expected = int(44100 * 3.0)
        assert len(audio) == expected

    def test_not_silent(self) -> None:
        audio = generate_pad("tense", duration_sec=2.0)
        assert np.max(np.abs(audio)) > 0.01

    def test_silence_preset_is_quiet(self) -> None:
        audio = generate_pad("silence", duration_sec=2.0)
        assert np.max(np.abs(audio)) < 0.001

    def test_no_clipping(self) -> None:
        for preset_name in list_presets():
            audio = generate_pad(preset_name, duration_sec=2.0)
            assert np.max(np.abs(audio)) <= 1.0, f"{preset_name} clips!"

    def test_writes_wav_file(self, tmp_path) -> None:
        out = tmp_path / "pad.wav"
        generate_pad("wonder", duration_sec=2.0, output_path=out)
        assert out.exists()
        assert out.stat().st_size > 1000  # Not empty

    def test_creates_parent_dirs(self, tmp_path) -> None:
        out = tmp_path / "deep" / "nested" / "pad.wav"
        generate_pad("contemplative", duration_sec=1.0, output_path=out)
        assert out.exists()

    def test_seed_reproducibility(self) -> None:
        a = generate_pad("tense", duration_sec=2.0, seed=42)
        b = generate_pad("tense", duration_sec=2.0, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_different_seeds_differ(self) -> None:
        a = generate_pad("tense", duration_sec=2.0, seed=42)
        b = generate_pad("tense", duration_sec=2.0, seed=99)
        assert not np.array_equal(a, b)

    def test_custom_preset(self) -> None:
        custom = PadPreset(
            name="custom",
            base_freq=220.0,
            base_amplitude=0.5,
            noise_amplitude=0.1,
        )
        audio = generate_pad(custom, duration_sec=2.0)
        assert np.max(np.abs(audio)) > 0.01

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            generate_pad("nonexistent", duration_sec=1.0)

    def test_all_presets_generate(self) -> None:
        """Smoke test: every preset generates without error."""
        for name in list_presets():
            audio = generate_pad(name, duration_sec=1.0)
            assert len(audio) > 0, f"Preset {name} produced empty audio"
