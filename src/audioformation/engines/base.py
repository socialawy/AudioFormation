"""
Abstract base class for TTS engines.

All engines implement this interface. Pipeline code calls engines
through this contract — never directly. Swapping engines requires
zero changes to pipeline logic.

TODO(Phase 2): Cloud engine integration
  - [ ] ElevenLabs engine adapter (high quality, API key required)
  - [ ] OpenAI TTS engine adapter (GPT-4o voice, API key required)
  - [ ] Cloud engine fallback (rate limiting, quota management)
  - [ ] Async batching for cloud API efficiency
  - [ ] Voice preview/download caching
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GenerationRequest:
    """Input to a TTS engine."""

    text: str
    output_path: Path
    voice: str | None = None
    language: str = "ar"
    reference_audio: Path | None = None
    direction: dict[str, str] | None = None

    # Engine-specific overrides (passed through)
    params: dict[str, Any] | None = None


@dataclass
class GenerationResult:
    """Output from a TTS engine."""

    success: bool
    output_path: Path | None = None
    duration_sec: float = 0.0
    sample_rate: int = 0
    error: str | None = None


class TTSEngine(ABC):
    """Abstract interface for text-to-speech engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier (e.g., 'edge', 'xtts', 'elevenlabs')."""
        ...

    @property
    @abstractmethod
    def supports_cloning(self) -> bool:
        """Whether this engine supports voice cloning from reference audio."""
        ...

    @property
    @abstractmethod
    def supports_ssml(self) -> bool:
        """Whether this engine supports SSML markup."""
        ...

    @property
    @abstractmethod
    def requires_gpu(self) -> bool:
        """Whether this engine requires (or strongly benefits from) a GPU."""
        ...

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate audio from text.

        Args:
            request: The generation parameters.

        Returns:
            GenerationResult with success status and output path.
        """
        ...

    @abstractmethod
    async def list_voices(self, language: str | None = None) -> list[dict[str, str]]:
        """
        List available voices, optionally filtered by language.

        Returns list of dicts with at least 'id' and 'name' keys.
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Verify the engine is available and functional.

        Returns True if engine is ready, False otherwise.
        """
        ...