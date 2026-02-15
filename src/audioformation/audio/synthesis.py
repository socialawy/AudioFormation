
"""
DSP Synthesis Primitives.

Shared signal processing functions for Composer (Music) and FXForge (SFX).
"""

import numpy as np


def oscillator(
    freq: float,
    duration_sec: float,
    sr: int,
    wave_type: str = "sine"
) -> np.ndarray:
    """Generate a basic waveform."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    phase = 2 * np.pi * freq * t

    if wave_type == "sine":
        return np.sin(phase)
    elif wave_type == "triangle":
        return 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
    elif wave_type == "saw":
        return 2 * (t * freq - np.floor(t * freq + 0.5))
    elif wave_type == "square":
        return np.sign(np.sin(phase))
    else:
        return np.sin(phase)


def cents_to_ratio(cents: float) -> float:
    """Convert cents detune to frequency ratio."""
    return 2 ** (cents / 1200)


def generate_noise(
    n_samples: int,
    color: str,
    rng: np.random.Generator
) -> np.ndarray:
    """Generate colored noise (white, pink, brown)."""
    if color == "white":
        white = rng.standard_normal(n_samples)
        return _normalize(white)
    
    elif color == "pink":
        # Simplified pink noise (1/f) approximation
        white = rng.standard_normal(n_samples)
        # Apply rolling average for pinkening
        kernel_size = 64
        kernel = np.ones(kernel_size) / kernel_size
        pink = np.convolve(white, kernel, mode='same')
        return _normalize(pink)

    elif color == "brown":
        # Brownian noise (1/f^2) via cumulative sum
        white = rng.standard_normal(n_samples)
        brown = np.cumsum(white)
        # High-pass to remove DC drift
        brown = brown - np.linspace(brown[0], brown[-1], n_samples)
        return _normalize(brown)
        
    else:
        return rng.standard_normal(n_samples)


def simple_lowpass(signal: np.ndarray, cutoff_hz: float, sr: int) -> np.ndarray:
    """Apply a simple first-order IIR lowpass filter."""
    if cutoff_hz >= sr / 2:
        return signal
        
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)

    out = np.zeros_like(signal)
    out[0] = alpha * signal[0]
    for i in range(1, len(signal)):
        out[i] = out[i - 1] + alpha * (signal[i] - out[i - 1])
    return out


def simple_highpass(signal: np.ndarray, cutoff_hz: float, sr: int) -> np.ndarray:
    """Apply a simple first-order IIR highpass filter."""
    if cutoff_hz <= 0:
        return signal

    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = rc / (rc + dt)

    out = np.zeros_like(signal)
    out[0] = signal[0]
    for i in range(1, len(signal)):
        out[i] = alpha * (out[i - 1] + signal[i] - signal[i - 1])
    return out


def apply_envelope(
    signal: np.ndarray,
    sr: int,
    fade_in_sec: float,
    fade_out_sec: float,
    curve: str = "linear"
) -> np.ndarray:
    """Apply fade-in and fade-out envelope."""
    n = len(signal)
    envelope = np.ones(n)

    fade_in_samples = int(fade_in_sec * sr)
    fade_out_samples = int(fade_out_sec * sr)

    if fade_in_samples > 0:
        fade_in_samples = min(fade_in_samples, n)
        if curve == "exponential":
            # x^2 curve
            envelope[:fade_in_samples] = np.linspace(0, 1, fade_in_samples) ** 2
        else:
            envelope[:fade_in_samples] = np.linspace(0, 1, fade_in_samples)

    if fade_out_samples > 0:
        fade_out_samples = min(fade_out_samples, n)
        if curve == "exponential":
            envelope[-fade_out_samples:] = np.linspace(1, 0, fade_out_samples) ** 2
        else:
            envelope[-fade_out_samples:] = np.linspace(1, 0, fade_out_samples)

    return signal * envelope


def _normalize(signal: np.ndarray) -> np.ndarray:
    """Normalize signal to -1.0 to 1.0 range."""
    peak = np.max(np.abs(signal))
    if peak > 0:
        return signal / peak
    return signal
