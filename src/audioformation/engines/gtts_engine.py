"""
gTTS (Google Translate TTS) — emergency fallback engine.

Not as high quality as edge-tts, but works with zero authentication.
Supports Arabic and English. No SSML. No voice selection.
Used when edge-tts is unavailable (403 / token expiry).
"""

from pathlib import Path
from typing import Any

from audioformation.engines.base import (
    TTSEngine,
    GenerationRequest,
    GenerationResult,
)


class GTTSEngine(TTSEngine):
    """Google Translate TTS fallback engine."""

    @property
    def name(self) -> str:
        return "gtts"

    @property
    def supports_cloning(self) -> bool:
        return False

    @property
    def supports_ssml(self) -> bool:
        return False

    @property
    def requires_gpu(self) -> bool:
        return False

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate audio using gTTS."""
        try:
            from gtts import gTTS

            lang = request.language or "ar"
            # gTTS language codes
            lang_map = {"ar": "ar", "en": "en"}
            gtts_lang = lang_map.get(lang, lang)

            tts = gTTS(text=request.text, lang=gtts_lang, slow=False)

            # gTTS outputs MP3
            output_path = request.output_path

            if output_path.suffix.lower() == ".wav":
                mp3_temp = output_path.with_suffix(".mp3")
                tts.save(str(mp3_temp))

                # Convert to WAV
                ok = _mp3_to_wav(mp3_temp, output_path)
                mp3_temp.unlink(missing_ok=True)

                if not ok:
                    return GenerationResult(
                        success=False,
                        error="Failed to convert gTTS MP3 to WAV.",
                    )
            else:
                tts.save(str(output_path))

            if not output_path.exists() or output_path.stat().st_size == 0:
                return GenerationResult(
                    success=False,
                    error="gTTS produced empty output.",
                )

            duration = _get_duration(output_path)

            return GenerationResult(
                success=True,
                output_path=output_path,
                duration_sec=duration,
                sample_rate=24000,
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"gTTS error: {type(e).__name__}: {e}",
            )

    async def list_voices(self, language: str | None = None) -> list[dict[str, str]]:
        """gTTS doesn't have selectable voices."""
        voices = [
            {"id": "ar", "name": "Arabic (Google)", "locale": "ar", "gender": "Unknown"},
            {"id": "en", "name": "English (Google)", "locale": "en", "gender": "Unknown"},
        ]
        if language:
            voices = [v for v in voices if v["locale"].startswith(language)]
        return voices

    async def test_connection(self) -> bool:
        """Test gTTS availability."""
        try:
            from gtts import gTTS
            # Quick test — just instantiate, don't generate
            gTTS(text="test", lang="en")
            return True
        except Exception:
            return False


def _mp3_to_wav(mp3_path: Path, wav_path: Path) -> bool:
    """Convert MP3 to WAV using pydub."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(str(mp3_path))
        audio.export(str(wav_path), format="wav")
        return wav_path.exists() and wav_path.stat().st_size > 0
    except Exception:
        return False


def _get_duration(path: Path) -> float:
    """Get audio duration in seconds."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(path))
        return len(audio) / 1000.0
    except Exception:
        return 0.0