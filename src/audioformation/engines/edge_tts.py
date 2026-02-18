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
        """
        voice = request.voice or "ar-SA-HamedNeural"
        output_path = request.output_path

        # Create unique temp file to avoid conflicts
        temp_id = uuid.uuid4().hex[:8]
        mp3_temp = output_path.parent / f"{output_path.stem}_tmp_{temp_id}.mp3"

        try:
            # Build SSML or plain text
            use_ssml = (
                request.direction
                and request.params
                and request.params.get("ssml", True)
            )

            if use_ssml:
                # Add unicode safeguard for direction config values
                direction = {
                    k: v for k, v in request.direction.items() if isinstance(v, str)
                }
                text = direction_to_ssml(request.text, direction)
            else:
                text = request.text

            # Edge-tts communication and save
            communicate = edge_tts.Communicate(text, voice)
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

_PACE_MAP: dict[str, str] = {
    "very slow": "x-slow",
    "slow": "slow",
    "moderate": "medium",
    "fast": "fast",
    "very fast": "x-fast",
}

_ENERGY_MAP: dict[str, str] = {
    "whisper": "x-soft",
    "quiet": "soft",
    "quiet contemplation": "soft",
    "normal": "medium",
    "loud": "loud",
    "intense": "x-loud",
}

_EMOTION_PITCH_MAP: dict[str, str] = {
    "wonder": "+5%",
    "sadness": "-5%",
    "tension": "+10%",
    "contemplation": "-2%",
    "triumph": "+8%",
    "melancholy": "-8%",
    "neutral": "+0%",
    "confrontation": "+5%",
}


def direction_to_ssml(text: str, direction: dict[str, str]) -> str:
    """
    Wrap text in SSML tags based on direction config.

    Maps direction fields (pace, energy, emotion) to SSML prosody attributes.
    Adds breaks for ellipsis, em dashes, and paragraph breaks.
    """
    pace = direction.get("pace", "").lower().strip()
    energy = direction.get("energy", "").lower().strip()
    emotion = direction.get("emotion", "").lower().strip()

    attrs: list[str] = []

    rate = _PACE_MAP.get(pace)
    if rate and rate != "medium":
        attrs.append(f'rate="{rate}"')

    volume = _ENERGY_MAP.get(energy)
    if volume and volume != "medium":
        attrs.append(f'volume="{volume}"')

    pitch = _EMOTION_PITCH_MAP.get(emotion)
    if pitch and pitch != "+0%":
        attrs.append(f'pitch="{pitch}"')

    processed = _process_inline_markers(text)

    if attrs:
        attr_str = " ".join(attrs)
        body = f"<prosody {attr_str}>{processed}</prosody>"
    else:
        body = processed

    return f"<speak>{body}</speak>"


def _process_inline_markers(text: str) -> str:
    """Replace inline markers with SSML breaks."""
    text = text.replace("...", '<break time="400ms"/>')
    text = text.replace("\u2026", '<break time="400ms"/>')
    text = text.replace("\u2014", '<break time="250ms"/>')  # em dash
    text = text.replace("\u2013", '<break time="200ms"/>')  # en dash
    text = text.replace("\n\n", '<break time="600ms"/>')
    return text
