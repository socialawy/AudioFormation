"""
Edge TTS engine adapter.

Priority 1: Free, fast, excellent Arabic voices.
Supports SSML for direction mapping (pace, energy, emotion).
Async-native via edge-tts library.

NOTE: edge-tts always outputs MP3 format regardless of file extension.
This adapter saves as .mp3 first, then converts to WAV for pipeline
consistency (all internal audio is WAV).
"""

import shutil
import uuid
from pathlib import Path

import edge_tts

from audioformation.engines.base import (
    TTSEngine,
    GenerationRequest,
    GenerationResult,
)


class EdgeTTSEngine(TTSEngine):
    """Edge TTS adapter using Microsoft's free neural voices."""

    @property
    def name(self) -> str:
        return "edge"

    @property
    def supports_cloning(self) -> bool:
        return False

    @property
    def supports_ssml(self) -> bool:
        return True

    @property
    def requires_gpu(self) -> bool:
        return False

    @property
    def requires_api_key(self) -> bool:
        return False

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate audio using edge-tts.

        Edge-tts always outputs MP3. If the requested output is .wav,
        we save as MP3 first then convert.

        Direction mapping uses edge-tts native rate/volume/pitch params
        instead of manual SSML (edge-tts wraps text in SSML internally).
        """
        voice = request.voice or "ar-SA-HamedNeural"
        output_path = request.output_path

        # Create unique temp file to avoid conflicts
        temp_id = uuid.uuid4().hex[:8]
        mp3_temp = output_path.parent / f"{output_path.stem}_tmp_{temp_id}.mp3"

        try:
            # Map direction to edge-tts native params
            rate_str = "+0%"
            volume_str = "+0%"
            pitch_str = "+0Hz"

            if request.direction:
                direction = {
                    k: v for k, v in request.direction.items() if isinstance(v, str)
                }
                rate_str, volume_str, pitch_str = _direction_to_params(direction)

            # Process inline markers (replace ellipsis/dashes with pauses)
            text = _process_inline_markers_plain(request.text)

            # Edge-tts communication and save (uses native SSML params)
            communicate = edge_tts.Communicate(
                text, voice, rate=rate_str, volume=volume_str, pitch=pitch_str
            )
            await communicate.save(str(mp3_temp))

            # Convert MP3 → WAV if needed
            if output_path.suffix.lower() == ".wav":
                ok = _mp3_to_wav(mp3_temp, output_path)
                # Clean up temp MP3 after successful conversion
                mp3_temp.unlink(missing_ok=True)
                if not ok:
                    return GenerationResult(
                        success=False,
                        error="Failed to convert edge-tts MP3 to WAV.",
                    )
            else:
                # Just move MP3 to final location
                shutil.move(str(mp3_temp), str(output_path))

            # Get duration
            duration = _get_duration(output_path)

            return GenerationResult(
                success=True,
                output_path=output_path,
                duration_sec=duration,
                sample_rate=24000,
            )

        except Exception as e:
            # Clean up any temp files on failure
            if "mp3_temp" in locals():
                try:
                    mp3_temp.unlink(missing_ok=True)
                except Exception:
                    pass

            return GenerationResult(
                success=False,
                error=f"edge-tts error: {type(e).__name__}: {e}",
            )

    async def list_voices(self, language: str | None = None) -> list[dict[str, str]]:
        """List available edge-tts voices, optionally filtered by language."""
        voices = await edge_tts.list_voices()

        results = []
        for v in voices:
            if language and not v["Locale"].startswith(language):
                continue
            results.append(
                {
                    "id": v["ShortName"],
                    "name": v["FriendlyName"],
                    "locale": v["Locale"],
                    "gender": v["Gender"],
                }
            )

        return results

    async def test_connection(self) -> bool:
        """Test edge-tts by listing voices."""
        try:
            voices = await edge_tts.list_voices()
            return len(voices) > 0
        except Exception:
            return False


# ──────────────────────────────────────────────
# Format conversion
# ──────────────────────────────────────────────


def _mp3_to_wav(mp3_path: Path, wav_path: Path) -> bool:
    """Convert MP3 to WAV using pydub."""
    try:
        from pydub import AudioSegment

        # Check input file
        if not mp3_path.exists() or mp3_path.stat().st_size == 0:
            return False

        # Load MP3 and convert to WAV
        audio = AudioSegment.from_mp3(str(mp3_path))
        audio.export(str(wav_path), format="wav")

        return wav_path.exists() and wav_path.stat().st_size > 0

    except Exception:
        return False


def _get_duration(path: Path) -> float:
    """Get audio duration in seconds using pydub."""
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(str(path))
        return len(audio) / 1000.0
    except Exception:
        return 0.0


# ──────────────────────────────────────────────
# SSML Direction Mapping
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# Direction → edge-tts native params
# ──────────────────────────────────────────────

# Rate maps to edge-tts rate param (percentage offset)
_PACE_RATE_MAP: dict[str, str] = {
    "very slow": "-50%",
    "slow": "-25%",
    "moderate": "+0%",
    "fast": "+25%",
    "very fast": "+50%",
}

# Energy maps to edge-tts volume param (percentage offset)
_ENERGY_VOLUME_MAP: dict[str, str] = {
    "whisper": "-80%",
    "quiet": "-40%",
    "quiet contemplation": "-30%",
    "calm": "-15%",
    "normal": "+0%",
    "loud": "+30%",
    "intense": "+50%",
}

# Emotion maps to edge-tts pitch param (Hz offset)
_EMOTION_PITCH_MAP: dict[str, str] = {
    "wonder": "+10Hz",
    "sadness": "-10Hz",
    "tension": "+20Hz",
    "contemplation": "-5Hz",
    "contemplative": "-5Hz",
    "triumph": "+15Hz",
    "melancholy": "-15Hz",
    "neutral": "+0Hz",
    "confrontation": "+10Hz",
}


def _direction_to_params(
    direction: dict[str, str],
) -> tuple[str, str, str]:
    """
    Map direction config to edge-tts native rate/volume/pitch params.

    Returns (rate, volume, pitch) strings for edge_tts.Communicate().
    """
    pace = direction.get("pace", "").lower().strip()
    energy = direction.get("energy", "").lower().strip()
    emotion = direction.get("emotion", "").lower().strip()

    rate = _PACE_RATE_MAP.get(pace, "+0%")
    volume = _ENERGY_VOLUME_MAP.get(energy, "+0%")
    pitch = _EMOTION_PITCH_MAP.get(emotion, "+0Hz")

    return rate, volume, pitch


def _process_inline_markers_plain(text: str) -> str:
    """Normalize inline markers for plain-text TTS input."""
    # Normalize ellipsis to three dots (TTS handles pauses naturally)
    text = text.replace("\u2026", "...")
    # Em/en dashes to comma-space (natural pause)
    text = text.replace("\u2014", ", ")
    text = text.replace("\u2013", ", ")
    return text
