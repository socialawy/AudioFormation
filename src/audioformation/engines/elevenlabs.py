"""
ElevenLabs TTS engine adapter.

High-quality cloud TTS with voice cloning capabilities.
Requires API key from https://elevenlabs.io/
Supports multiple languages including Arabic.
Rate limiting: 10 requests/minute (free tier).

TODO(Phase 2): Advanced features
  - [ ] Voice cloning from reference audio
  - [ ] Voice settings (stability, similarity, style)
  - [ ] Streaming generation for long texts
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx

from audioformation.engines.base import (
    TTSEngine,
    GenerationRequest,
    GenerationResult,
)


class ElevenLabsEngine(TTSEngine):
    """ElevenLabs cloud TTS adapter."""

    def __init__(self, api_key: str | None = None):
        """Initialize ElevenLabs engine.

        Args:
            api_key: ElevenLabs API key. If None, reads from ELEVENLABS_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY environment variable."
            )

        self.base_url = "https://api.elevenlabs.io/v1"
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def supports_cloning(self) -> bool:
        return True  # ElevenLabs supports voice cloning

    @property
    def supports_ssml(self) -> bool:
        return False  # ElevenLabs uses their own markup, not standard SSML

    @property
    def requires_gpu(self) -> bool:
        return False  # Cloud-based, no GPU required

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"xi-api-key": self.api_key},
                timeout=30.0,
            )
        return self._client

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate audio using ElevenLabs API."""
        client = await self._get_client()
        voice = request.voice or "rachel"  # Default voice

        try:
            # Map language codes to ElevenLabs voice IDs
            voice_id = await self._get_voice_id(voice, request.language)

            # Prepare generation request
            payload = {
                "text": request.text,
                "model_id": "eleven_multilingual_v2",  # Best for Arabic/English
                "voice_settings": {
                    "stability": 0.75,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            }

            # Add voice cloning if reference audio provided
            if request.reference_audio and request.reference_audio.exists():
                # For now, use provided voice ID
                # TODO: Implement actual voice cloning workflow
                pass

            # Generate audio
            response = await client.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                json=payload,
            )
            response.raise_for_status()

            # Save audio (ElevenLabs returns MP3)
            output_path = request.output_path

            if output_path.suffix.lower() == ".wav":
                # Save as MP3 first, then convert
                mp3_temp = output_path.with_suffix(".mp3")
                with open(mp3_temp, "wb") as f:
                    f.write(response.content)

                # Convert to WAV using ffmpeg
                success = await self._mp3_to_wav(mp3_temp, output_path)
                mp3_temp.unlink(missing_ok=True)

                if not success:
                    return GenerationResult(
                        success=False,
                        error="Failed to convert ElevenLabs MP3 to WAV",
                    )
            else:
                with open(output_path, "wb") as f:
                    f.write(response.content)

            # Get audio duration
            duration = await self._get_duration(output_path)

            return GenerationResult(
                success=True,
                output_path=output_path,
                duration_sec=duration,
                sample_rate=44100,  # ElevenLabs standard
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                error = "Invalid ElevenLabs API key"
            elif e.response.status_code == 429:
                error = "ElevenLabs rate limit exceeded (10 req/min free tier)"
            elif e.response.status_code == 400:
                error = f"Invalid request to ElevenLabs: {e.response.text}"
            else:
                error = f"ElevenLabs API error: {e.response.status_code}"

            return GenerationResult(success=False, error=error)

        except Exception as e:
            return GenerationResult(
                success=False, error=f"ElevenLabs generation failed: {e}"
            )

    async def list_voices(self, language: str | None = None) -> list[dict[str, str]]:
        """List available ElevenLabs voices."""
        client = await self._get_client()

        try:
            response = await client.get(f"{self.base_url}/voices")
            response.raise_for_status()

            voices_data = response.json()
            voices = []

            for voice in voices_data.get("voices", []):
                # Filter by language if specified
                if language:
                    lang_map = {"ar": "arabic", "en": "english"}
                    target_lang = lang_map.get(language, language)
                    if target_lang not in voice.get("language", "").lower():
                        continue

                voices.append(
                    {
                        "id": voice["voice_id"],
                        "name": voice["name"],
                        "language": voice.get("language", "unknown"),
                        "gender": voice.get("gender", "unknown"),
                    }
                )

            return voices

        except Exception:
            # Return empty list on error
            return []

    async def test_connection(self) -> bool:
        """Test ElevenLabs API connection."""
        try:
            voices = await self.list_voices()
            return len(voices) > 0
        except Exception:
            return False

    async def _get_voice_id(self, voice: str, language: str | None = None) -> str:
        """Get voice ID by name or return as-is if already an ID."""
        # If it looks like a UUID, return as-is
        if len(voice) == 32 and "-" not in voice:
            return voice

        # Search for voice by name
        voices = await self.list_voices(language)
        for v in voices:
            if v["name"].lower() == voice.lower():
                return v["id"]

        # Default voices by language
        defaults = {
            "ar": "pNInz6obpgDQGcFmaJgB",  # Adam (Arabic)
            "en": "rachel",  # Rachel (English)
        }

        return defaults.get(language or "en", voice)

    async def _mp3_to_wav(self, mp3_path: Path, wav_path: Path) -> bool:
        """Convert MP3 to WAV using ffmpeg."""
        try:

            cmd = [
                "ffmpeg",
                "-i",
                str(mp3_path),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "44100",
                "-ac",
                "1",
                str(wav_path),
                "-y",  # Overwrite
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            return result.returncode == 0 and wav_path.exists()

        except Exception:
            return False

    async def _get_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        try:

            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                return float(stdout.decode().strip())

        except Exception:
            pass

        return 0.0

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
