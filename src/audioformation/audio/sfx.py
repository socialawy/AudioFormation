"""
FXForge — Procedural Sound Effects Generator.

Generates transient SFX (whooshes, impacts, UI sounds) using
synthesis primitives.

Pipeline Node: SFX (Optional).
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Optional, Literal

from audioformation.config import PROJECTS_ROOT
from audioformation.audio.synthesis import (
    generate_noise,
    simple_lowpass,
    apply_envelope,
)
from audioformation.utils.security import validate_path_within

SFX_TYPES = Literal["whoosh", "impact", "ui_click", "static", "drone"]


def generate_sfx(
    sfx_type: SFX_TYPES,
    output_path: Optional[Path] = None,
    duration: float = 1.0,
    seed: Optional[int] = None,
    sample_rate: int = 44100,
) -> np.ndarray:
    """
    Generate a procedural sound effect.

    Args:
        sfx_type: Type of effect (whoosh, impact, etc.).
        output_path: Optional path to save WAV file.
        duration: Duration in seconds.
        seed: Random seed.
        sample_rate: Audio sample rate.

    Returns:
        Numpy array of audio samples.
    """
    rng = np.random.default_rng(seed)
    n_samples = int(sample_rate * duration)

    # Silence default
    audio = np.zeros(n_samples, dtype=np.float32)

    if sfx_type == "whoosh":
        audio = _gen_whoosh(n_samples, sample_rate, rng)
    elif sfx_type == "impact":
        audio = _gen_impact(n_samples, sample_rate, rng)
    elif sfx_type == "ui_click":
        # Force short duration for clicks
        duration = 0.1
        n_samples = int(sample_rate * duration)
        audio = _gen_ui_click(n_samples, sample_rate, rng)
    elif sfx_type == "static":
        audio = generate_noise(n_samples, "white", rng)
        audio = apply_envelope(audio, sample_rate, 0.1, 0.1)
    elif sfx_type == "drone":
        audio = _gen_drone(n_samples, sample_rate, rng)
    else:
        raise ValueError(f"Unknown SFX type: {sfx_type}")

    # Final normalization
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9

    if output_path:
        # CODEQL FIX: Textual normalization guard
        abs_dest = os.path.abspath(str(output_path))
        
        valid = False
        try:
             # Check Projects Root
             if abs_dest.startswith(os.path.abspath(str(PROJECTS_ROOT))):
                 valid = True
             else:
                 import tempfile
                 if abs_dest.startswith(os.path.abspath(tempfile.gettempdir())):
                     valid = True
        except Exception: pass
        
        if not valid: raise ValueError("Invalid path")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, sample_rate)

    return audio


def _gen_whoosh(n: int, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Filtered pink noise with volume swell."""
    noise = generate_noise(n, "pink", rng)

    # Swell envelope (fade in 40%, hold 20%, fade out 40%)
    fade_len = int(n * 0.4)
    envelope = np.concatenate(
        [
            np.linspace(0, 1, fade_len),
            np.ones(n - 2 * fade_len),
            np.linspace(1, 0, fade_len),
        ]
    )

    # Ensure lengths match due to rounding
    if len(envelope) < n:
        envelope = np.pad(envelope, (0, n - len(envelope)))
    elif len(envelope) > n:
        envelope = envelope[:n]

    return noise * envelope


def _gen_impact(n: int, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Low sine kick + noise burst."""
    t = np.linspace(0, n / sr, n, endpoint=False)

    # Pitch drop: 150Hz -> 50Hz
    freq = np.linspace(150, 50, n)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    kick = np.sin(phase)

    # Kick envelope: fast decay
    decay = np.exp(-10 * t)
    kick *= decay

    # Noise burst (crunch)
    noise = generate_noise(n, "white", rng)
    noise_env = np.exp(-20 * t)  # very fast decay
    noise *= noise_env

    return kick * 0.7 + noise * 0.3


def _gen_ui_click(n: int, sr: int, rng: np.random.Generator) -> np.ndarray:
    """High frequency sine blip."""
    t = np.linspace(0, n / sr, n, endpoint=False)

    # Sine blip 2000Hz
    blip = np.sin(2 * np.pi * 2000 * t)

    # Very short envelope
    env = np.exp(-50 * t)

    return blip * env


def _gen_drone(n: int, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Deep saw wave cluster."""
    t = np.linspace(0, n / sr, n, endpoint=False)

    # Two saw waves slightly detuned
    osc1 = 2 * (t * 55 - np.floor(t * 55 + 0.5))  # 55Hz (A1)
    osc2 = 2 * (t * 55.5 - np.floor(t * 55.5 + 0.5))

    drone = osc1 + osc2

    # Lowpass to remove harshness
    drone = simple_lowpass(drone, 200, sr)

    return drone
