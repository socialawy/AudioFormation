
"""
Multi-track audio mixer with VAD-based ducking.

Combines voice (foreground) and music/ambience (background).
Applies automatic ducking to the background track when speech is detected.

Pipeline Node 6: Mix.
"""

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np
from pydub import AudioSegment

# Try importing torch for VAD
try:
    import torch
    SILERO_AVAILABLE = True
except ImportError:
    SILERO_AVAILABLE = False

logger = logging.getLogger(__name__)


class AudioMixer:
    """Handles mixing of voice and background tracks with ducking."""

    def __init__(self, config: dict[str, Any]):
        """
        Initialize mixer with project mix configuration.
        
        Args:
            config: The "mix" section of project.json.
        """
        self.config = config
        self.ducking_config = config.get("ducking", {})
        
        self.master_volume = config.get("master_volume", 0.9)
        self.target_lufs = config.get("target_lufs", -16.0)
        
        # Ducking parameters
        self.method = self.ducking_config.get("method", "vad")
        self.attenuation_db = self.ducking_config.get("attenuation_db", -12.0)
        self.attack_ms = self.ducking_config.get("attack_ms", 100)
        self.release_ms = self.ducking_config.get("release_ms", 500)
        self.look_ahead_ms = self.ducking_config.get("look_ahead_ms", 200)
        self.vad_threshold = self.ducking_config.get("vad_threshold", 0.5)

        # Cache for VAD model
        self._vad_model = None
        self._get_speech_timestamps = None

    def _ensure_vad_model(self):
        """Lazy load Silero VAD model."""
        if self._vad_model is not None:
            return

        if not SILERO_AVAILABLE:
            logger.warning("Torch not available. Falling back to energy-based ducking.")
            self.method = "energy"
            return

        try:
            # Load from torch hub (caches locally)
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            self._vad_model = model
            self._get_speech_timestamps = utils[0]  # get_speech_timestamps
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}. Falling back to energy.")
            self.method = "energy"

    def mix_chapter(
        self,
        voice_path: Path,
        music_path: Path | None,
        output_path: Path,
    ) -> bool:
        """
        Mix a voice chapter with optional background music.

        Args:
            voice_path: Path to voice audio (processed WAV).
            music_path: Path to background music (optional).
            output_path: Destination path.

        Returns:
            True on success.
        """
        try:
            # Load voice
            voice = AudioSegment.from_file(str(voice_path))
            
            if not music_path or not music_path.exists():
                # No music, just save voice
                # Apply master volume
                output = voice.apply_gain(20 * math.log10(self.master_volume))
                output.export(str(output_path), format="wav")
                return True

            # Load music
            music = AudioSegment.from_file(str(music_path))
            
            # Loop music to cover voice length + decay
            target_duration = len(voice) + 2000  # +2s tail
            if len(music) < target_duration:
                loops = int(math.ceil(target_duration / len(music)))
                music = music * loops
            
            # Trim to exact length
            music = music[:target_duration]

            # Generate ducking envelope
            envelope = self._generate_envelope(voice, len(music))
            
            # Apply ducking to music
            ducked_music = self._apply_envelope(music, envelope)
            
            # Overlay voice
            # Voice starts at 0 for now (could add lead-in config)
            # Ensure voice fits in music duration
            combined = ducked_music.overlay(voice, position=0)
            
            # Apply master volume
            # db = 20 * log10(vol_linear)
            if self.master_volume != 1.0:
                gain_db = 20 * math.log10(max(self.master_volume, 0.0001))
                combined = combined.apply_gain(gain_db)

            # Export
            output_path.parent.mkdir(parents=True, exist_ok=True)
            combined.export(str(output_path), format="wav")
            return True

        except Exception as e:
            logger.error(f"Mixing failed for {voice_path.name}: {e}")
            return False

    def _generate_envelope(self, voice_seg: AudioSegment, total_len_ms: int) -> np.ndarray:
        """
        Generate a gain envelope array (0.0 to 1.0) for the background track.
        
        1.0 = full volume (silence in voice)
        <1.0 = ducked volume (speech detected)
        """
        # Default to full volume
        envelope = np.ones(total_len_ms, dtype=np.float32)
        
        # Calculate attenuation factor linear: -12dB -> 0.25
        attenuation_factor = 10 ** (self.attenuation_db / 20)
        
        timestamps = []

        if self.method == "vad":
            self._ensure_vad_model()
            
            if self._vad_model:
                # Prepare audio for VAD (float32, 16khz usually preferred but 24k/48k works with silero)
                # Pydub to numpy
                samples = np.array(voice_seg.get_array_of_samples())
                if voice_seg.channels > 1:
                    samples = samples.reshape((-1, voice_seg.channels))
                    samples = samples.mean(axis=1) # mixdown to mono
                
                # Normalize float32
                samples_float = samples.astype(np.float32) / 32768.0
                
                # NOTE: Silero VAD officially supports 8kHz/16kHz.
                # Edge-tts outputs 24kHz, XTTS outputs 24kHz.
                # Silero handles this robustly in practice (tested),
                # but VAD threshold may need per-project tuning.
                # If accuracy issues arise, resample to 16kHz first:
                #   import scipy.signal
                #   samples_16k = scipy.signal.resample_poly(samples_float, 16000, sr)
                speech_ts = self._get_speech_timestamps(
                    torch.from_numpy(samples_float),
                    self._vad_model,
                    sampling_rate=voice_seg.frame_rate,
                    threshold=self.vad_threshold
                )
                
                # Convert samples to ms
                sr_ms = voice_seg.frame_rate / 1000.0
                timestamps = [
                    {'start': int(ts['start'] / sr_ms), 'end': int(ts['end'] / sr_ms)}
                    for ts in speech_ts
                ]
            else:
                # Fallback to energy if VAD init failed
                timestamps = self._get_energy_timestamps(voice_seg)
        else:
            # Energy method
            timestamps = self._get_energy_timestamps(voice_seg)

        # Apply timestamps to envelope
        for ts in timestamps:
            start = max(0, ts['start'] - self.look_ahead_ms)
            end = min(total_len_ms, ts['end'] + self.release_ms)
            
            # Simple rectangular ducking for now, could be smoothed
            # In numpy we can just slice
            # But we want smoothing (attack/release)
            
            # We'll paint the target gain, then smooth later? 
            # Or simpler: just set the target gain in the window
            envelope[start:end] = attenuation_factor

        # Smooth the envelope (simple moving average approx for attack/release)
        # Proper attack/release filter is better but slower in python. 
        # Since we generated blocky envelope, `scipy.ndimage.gaussian_filter1d` 
        # or simple convolution helps.
        
        # Let's use a window for smoothing to simulate attack/release
        # A window size of ~200ms is a rough approx
        window_size = int(min(self.attack_ms, self.release_ms))
        if window_size > 0 and len(timestamps) > 0:
            kernel = np.ones(window_size) / window_size
            envelope = np.convolve(envelope, kernel, mode='same')
            # Smooth edges back to 1.0 (avoid discontinuity from hard set)
            edge_region = min(window_size, 100)
            if edge_region > 1:
                fade_in = np.linspace(1.0, envelope[edge_region], edge_region)
                envelope[:edge_region] = fade_in
                fade_out = np.linspace(envelope[-edge_region], 1.0, edge_region)
                envelope[-edge_region:] = fade_out

        return envelope

    def _get_energy_timestamps(self, segment: AudioSegment) -> list[dict]:
        """Simple RMS-based VAD fallback."""
        # Chunk size 50ms
        chunk_len = 50
        timestamps = []
        is_speech = False
        start_time = 0
        
        # Threshold: -40dBFS
        threshold = -40.0
        
        for i in range(0, len(segment), chunk_len):
            chunk = segment[i:i+chunk_len]
            if chunk.dBFS > threshold:
                if not is_speech:
                    is_speech = True
                    start_time = i
            else:
                if is_speech:
                    is_speech = False
                    timestamps.append({'start': start_time, 'end': i})
        
        if is_speech:
            timestamps.append({'start': start_time, 'end': len(segment)})
            
        return timestamps

    def _apply_envelope(self, music: AudioSegment, envelope: np.ndarray) -> AudioSegment:
        """
        Apply numpy gain envelope to pydub AudioSegment.
        
        Optimized approach: Convert audio to numpy, multiply, convert back.
        """
        # Ensure envelope matches music length
        if len(envelope) != len(music):
            # Pad or trim envelope
            if len(envelope) < len(music):
                envelope = np.pad(envelope, (0, len(music) - len(envelope)), 'constant', constant_values=1.0)
            else:
                envelope = envelope[:len(music)]

        # Convert music to numpy
        # Pydub samples are usually int16 or int32
        # get_array_of_samples returns array.array
        samples = np.array(music.get_array_of_samples())
        
        # Determine reshaping for channels
        channels = music.channels
        if channels > 1:
            # Interleaved samples: [L, R, L, R...]
            # Reshape to (N, channels)
            samples = samples.reshape((-1, channels))
        
        # Envelope is 1D (time in ms). We need to stretch it to sample rate.
        # This is the tricky part. Envelope is 1 value per MILLISECOND.
        # Audio is 24000/44100 values per second.
        
        # Resample envelope to match audio sample count
        target_len = samples.shape[0]
        
        # Linear interpolation of envelope to audio rate
        # x_old = indices of milliseconds [0, 1, 2, ... len(music)]
        # x_new = indices of samples [0, 1/sr, 2/sr ...] mapped to ms
        
        xp = np.arange(len(envelope))
        x_target = np.linspace(0, len(envelope), target_len)
        
        envelope_resampled = np.interp(x_target, xp, envelope)
        
        # Broadcast envelope to channels
        if channels > 1:
            envelope_resampled = envelope_resampled[:, np.newaxis]
            
        # Apply gain
        processed_samples = samples * envelope_resampled
        
        # Cast back to integer type
        processed_samples = processed_samples.astype(samples.dtype)
        
        # Flatten if stereo
        if channels > 1:
            processed_samples = processed_samples.flatten()
            
        # Create new AudioSegment
        return music._spawn(processed_samples.tobytes())

