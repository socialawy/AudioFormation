"""
Ambient pad generator — mood-based background audio for audiobooks.

ComposeEngine Tier 1: Pure numpy synthesis → WAV output.
Generates loopable, non-fatiguing ambient pads from oscillators,
filtered noise, and LFO modulation.

Pipeline Node 5: Compose.
"""

import numpy as np
import soundfile as sf
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from audioformation.audio.synthesis import (
    oscillator,
    cents_to_ratio,
    generate_noise,
    simple_lowpass,
    simple_highpass,
    apply_envelope,
)


# ---------------------------------------------------------------------------
# Mood presets
# ---------------------------------------------------------------------------


@dataclass
class PadPreset:
    """Configuration for an ambient pad sound."""

    name: str
    # Base tone
    base_freq: float = 110.0  # Hz
    base_type: str = "sine"  # sine, triangle, saw
    base_amplitude: float = 0.3
    # Second oscillator (detune for richness)
    detune_cents: float = 7.0  # slight detune for warmth
    detune_amplitude: float = 0.2
    # Sub bass
    sub_freq_ratio: float = 0.5  # relative to base
    sub_amplitude: float = 0.15
    # Noise layer
    noise_amplitude: float = 0.05
    noise_color: str = "pink"  # white, pink, brown
    # LFO modulation
    lfo_rate: float = 0.08  # Hz (very slow)
    lfo_depth: float = 0.3  # 0-1, modulation depth
    lfo_target: str = "amplitude"  # amplitude, pitch, filter
    # Filter
    lowpass_hz: float = 2000.0
    highpass_hz: float = 40.0
    # Envelope
    fade_in_sec: float = 3.0
    fade_out_sec: float = 3.0
    # Output
    sample_rate: int = 44100


MOOD_PRESETS: dict[str, PadPreset] = {
    "contemplative": PadPreset(
        name="contemplative",
        base_freq=130.81,  # C3
        base_type="sine",
        base_amplitude=0.25,
        detune_cents=5.0,
        detune_amplitude=0.15,
        sub_amplitude=0.1,
        noise_amplitude=0.03,
        noise_color="brown",
        lfo_rate=0.05,
        lfo_depth=0.2,
        lowpass_hz=1500,
        fade_in_sec=4.0,
        fade_out_sec=4.0,
    ),
    "tense": PadPreset(
        name="tense",
        base_freq=116.54,  # Bb2
        base_type="saw",
        base_amplitude=0.2,
        detune_cents=15.0,
        detune_amplitude=0.18,
        sub_freq_ratio=0.5,
        sub_amplitude=0.2,
        noise_amplitude=0.08,
        noise_color="pink",
        lfo_rate=0.12,
        lfo_depth=0.4,
        lowpass_hz=1200,
        highpass_hz=60,
        fade_in_sec=2.0,
        fade_out_sec=3.0,
    ),
    "wonder": PadPreset(
        name="wonder",
        base_freq=196.0,  # G3
        base_type="sine",
        base_amplitude=0.25,
        detune_cents=3.0,
        detune_amplitude=0.2,
        sub_amplitude=0.08,
        noise_amplitude=0.02,
        noise_color="white",
        lfo_rate=0.06,
        lfo_depth=0.25,
        lowpass_hz=3000,
        fade_in_sec=5.0,
        fade_out_sec=5.0,
    ),
    "melancholy": PadPreset(
        name="melancholy",
        base_freq=146.83,  # D3
        base_type="triangle",
        base_amplitude=0.22,
        detune_cents=8.0,
        detune_amplitude=0.15,
        sub_amplitude=0.12,
        noise_amplitude=0.04,
        noise_color="brown",
        lfo_rate=0.04,
        lfo_depth=0.35,
        lowpass_hz=1800,
        fade_in_sec=4.0,
        fade_out_sec=5.0,
    ),
    "triumph": PadPreset(
        name="triumph",
        base_freq=164.81,  # E3
        base_type="saw",
        base_amplitude=0.3,
        detune_cents=5.0,
        detune_amplitude=0.25,
        sub_freq_ratio=0.5,
        sub_amplitude=0.18,
        noise_amplitude=0.03,
        noise_color="pink",
        lfo_rate=0.07,
        lfo_depth=0.2,
        lowpass_hz=2500,
        highpass_hz=50,
        fade_in_sec=3.0,
        fade_out_sec=4.0,
    ),
    "silence": PadPreset(
        name="silence",
        base_amplitude=0.0,
        detune_amplitude=0.0,
        sub_amplitude=0.0,
        noise_amplitude=0.0,
    ),
}


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_pad(
    preset: str | PadPreset,
    duration_sec: float = 60.0,
    output_path: Optional[Path] = None,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Generate an ambient pad.

    Args:
        preset: Mood name (str) or PadPreset instance.
        duration_sec: Duration in seconds.
        output_path: If provided, writes WAV file.
        seed: Random seed for reproducibility.

    Returns:
        numpy array of audio samples (float32, mono).
    """
    if isinstance(preset, str):
        if preset not in MOOD_PRESETS:
            raise ValueError(
                f"Unknown preset '{preset}'. " f"Available: {list(MOOD_PRESETS.keys())}"
            )
        p = MOOD_PRESETS[preset]
    else:
        p = preset

    sr = p.sample_rate
    n_samples = int(sr * duration_sec)
    rng = np.random.default_rng(seed)

    # Start with silence
    mix = np.zeros(n_samples, dtype=np.float64)

    # Base oscillator
    if p.base_amplitude > 0:
        base = oscillator(p.base_freq, duration_sec, sr, p.base_type)
        mix += base * p.base_amplitude

    # Detuned oscillator for richness
    if p.detune_amplitude > 0:
        detune_freq = p.base_freq * cents_to_ratio(p.detune_cents)
        detuned = oscillator(detune_freq, duration_sec, sr, p.base_type)
        mix += detuned * p.detune_amplitude

    # Sub bass
    if p.sub_amplitude > 0:
        sub_freq = p.base_freq * p.sub_freq_ratio
        sub = oscillator(sub_freq, duration_sec, sr, "sine")
        mix += sub * p.sub_amplitude

    # Noise layer
    if p.noise_amplitude > 0:
        noise = generate_noise(n_samples, p.noise_color, rng)
        mix += noise * p.noise_amplitude

    # LFO modulation
    if p.lfo_depth > 0:
        lfo = oscillator(p.lfo_rate, duration_sec, sr, "sine")
        lfo = 1.0 - p.lfo_depth * 0.5 * (1.0 + lfo)  # range: [1-depth, 1]

        if p.lfo_target == "amplitude":
            mix *= lfo
        elif p.lfo_target == "pitch":
            # Subtle pitch wobble by resampling — skip for now, amplitude is fine
            mix *= lfo

    # Filtering
    if p.lowpass_hz < sr / 2:
        mix = simple_lowpass(mix, p.lowpass_hz, sr)
    if p.highpass_hz > 0:
        mix = simple_highpass(mix, p.highpass_hz, sr)

    # Envelope
    mix = apply_envelope(mix, sr, p.fade_in_sec, p.fade_out_sec)

    # Normalize to prevent clipping
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak * 0.85  # Leave headroom

    # Convert to float32
    mix = mix.astype(np.float32)

    # Write to file if requested
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), mix, sr)

    return mix


def list_presets() -> list[str]:
    """Return available mood preset names."""
    return list(MOOD_PRESETS.keys())


def get_preset(name: str) -> PadPreset:
    """Get a preset by name. Raises ValueError if not found."""
    if name not in MOOD_PRESETS:
        raise ValueError(
            f"Unknown preset '{name}'. Available: {list(MOOD_PRESETS.keys())}"
        )
    return MOOD_PRESETS[name]
