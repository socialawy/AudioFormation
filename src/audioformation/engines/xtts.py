"""
XTTS v2 engine adapter — local voice cloning via Coqui TTS (Idiap fork).

GPU-accelerated with CPU fallback. 17 languages including Arabic.
Requires reference audio (6–10s) for voice cloning.

VRAM profile (GTX 1650 Ti, 4GB):
  Model load:  ~2.0 GB
  Headroom:    ~1.5 GB
  Per chunk:   ~3.8s (Arabic, 200 chars)

VRAM strategies (set in generation.xtts_vram_management):
  empty_cache_per_chapter — keep model, clear cache (default)
  conservative            — unload model after every chapter
  reload_periodic         — unload/reload every N chapters

TODO(Phase 2): Voice cloning workflow enhancements
  - [ ] Batch reference audio validation (format, duration, quality)
  - [ ] Speaker similarity scoring against reference
  - [ ] Voice blending (multiple references → single voice)
  - [ ] Fine-tuning hooks for custom voice adaptation
  - [ ] Emotional tone control (happy, sad, neutral)
"""

import gc
import logging
import os
from pathlib import Path
from typing import Any

from audioformation.engines.base import (
    GenerationRequest,
    GenerationResult,
    TTSEngine,
)

logger = logging.getLogger(__name__)

# Accept CPML license non-interactively.
# User confirmed during the feasibility spike.
os.environ["COQUI_TOS_AGREED"] = "1"

_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

# Minimum free VRAM (GB) to attempt GPU loading.
_MIN_VRAM_GB = 3.0

# Languages XTTS v2 supports (for list_voices).
_SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"id": "ar", "name": "Arabic"},
    {"id": "en", "name": "English"},
    {"id": "cs", "name": "Czech"},
    {"id": "de", "name": "German"},
    {"id": "es", "name": "Spanish"},
    {"id": "fr", "name": "French"},
    {"id": "hi", "name": "Hindi"},
    {"id": "hu", "name": "Hungarian"},
    {"id": "it", "name": "Italian"},
    {"id": "ja", "name": "Japanese"},
    {"id": "ko", "name": "Korean"},
    {"id": "nl", "name": "Dutch"},
    {"id": "pl", "name": "Polish"},
    {"id": "pt", "name": "Portuguese"},
    {"id": "ru", "name": "Russian"},
    {"id": "tr", "name": "Turkish"},
    {"id": "zh-cn", "name": "Chinese"},
]


class XTTSEngine(TTSEngine):
    """XTTS v2 voice-cloning engine."""

    def __init__(self, device: str | None = None) -> None:
        self._model: Any = None
        self._device_preference = device  # None → auto-detect
        self._resolved_device: str | None = None
        self._generation_count = 0

    # ── TTSEngine properties ─────────────────────────────

    @property
    def name(self) -> str:
        return "xtts"

    @property
    def supports_cloning(self) -> bool:
        return True

    @property
    def supports_ssml(self) -> bool:
        return False

    @property
    def requires_gpu(self) -> bool:
        # Strongly benefits from GPU but works on CPU.
        return False

    @property
    def requires_api_key(self) -> bool:
        return False

    # ── Device management ────────────────────────────────

    @property
    def device(self) -> str:
        """Resolved device string ('cuda' or 'cpu'). Lazy."""
        if self._resolved_device is None:
            self._resolved_device = self._detect_device()
        return self._resolved_device

    def _detect_device(self) -> str:
        if self._device_preference:
            return (
                "cuda" if self._device_preference == "gpu" else self._device_preference
            )

        try:
            import torch

            if torch.cuda.is_available():
                free_gb = torch.cuda.mem_get_info()[0] / 1e9
                if free_gb >= _MIN_VRAM_GB:
                    logger.info("XTTS: using CUDA (%.1f GB free)", free_gb)
                    return "cuda"
                logger.warning(
                    "XTTS: only %.1f GB VRAM free (need %.1f), falling back to CPU",
                    free_gb,
                    _MIN_VRAM_GB,
                )
            return "cpu"
        except ImportError:
            return "cpu"

    # ── Model lifecycle ──────────────────────────────────

    def _ensure_model(self) -> Any:
        """Lazy-load the XTTS model. Cached after first call."""
        if self._model is not None:
            return self._model

        try:
            from TTS.api import TTS  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "coqui-tts is not installed. Run:  pip install coqui-tts"
            ) from exc

        logger.info("XTTS: loading %s on %s …", _MODEL_NAME, self.device)
        model = TTS(_MODEL_NAME)
        if self.device == "cuda":
            model.to("cuda")

        self._model = model
        logger.info("XTTS: model ready.")
        return self._model

    def release_vram(self) -> None:
        """
        Free GPU cache without unloading the model.

        Called between chapters under the *empty_cache_per_chapter*
        strategy.  Fast (~5 ms) and keeps the model warm.
        """
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                free_gb = torch.cuda.mem_get_info()[0] / 1e9
                logger.debug("XTTS: cache cleared — %.1f GB free", free_gb)
        except ImportError:
            pass

    def unload_model(self) -> None:
        """
        Fully evict model from GPU + RAM.

        Used by *conservative* and *reload_periodic* strategies.
        Next ``generate()`` call will reload from disk cache (~15 s).
        """
        if self._model is None:
            return

        del self._model
        self._model = None
        self._generation_count = 0
        self._resolved_device = None  # re-detect on next load

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        gc.collect()
        logger.info("XTTS: model unloaded.")

    # ── Generation ───────────────────────────────────────

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate audio via XTTS v2 voice cloning.

        ``request.reference_audio`` is **required** — XTTS has no
        built-in speaker presets.  The reference should be 6–10 s of
        clean speech from the target voice.
        """
        output_path = request.output_path
        language = _map_language(request.language or "ar")

        # ── Validate reference audio ──
        ref_audio = request.reference_audio
        if ref_audio is None:
            return GenerationResult(
                success=False,
                error=(
                    "XTTS requires reference_audio for voice cloning. "
                    "Set reference_audio in the character config or "
                    "use a different engine."
                ),
            )

        ref_path = Path(ref_audio)
        if not ref_path.exists():
            return GenerationResult(
                success=False,
                error=f"Reference audio not found: {ref_path}",
            )

        # ── Generation parameters (from project.json → params) ──
        params = request.params or {}
        temperature = float(params.get("temperature", 0.7))
        repetition_penalty = float(params.get("repetition_penalty", 5.0))

        try:
            model = self._ensure_model()

            # XTTS outputs WAV natively — no conversion needed.
            output_path.parent.mkdir(parents=True, exist_ok=True)

            model.tts_to_file(
                text=request.text,
                file_path=str(output_path),
                speaker_wav=str(ref_path),
                language=language,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )

            self._generation_count += 1

            if not output_path.exists() or output_path.stat().st_size == 0:
                return GenerationResult(
                    success=False,
                    error="XTTS produced empty output.",
                )

            duration = _get_duration(output_path)

            return GenerationResult(
                success=True,
                output_path=output_path,
                duration_sec=duration,
                sample_rate=24000,
            )

        except Exception as exc:
            msg = str(exc)

            # Surface CUDA OOM clearly.
            if "CUDA" in msg and ("out of memory" in msg or "OOM" in msg):
                logger.error("XTTS: CUDA OOM — releasing VRAM.")
                self.release_vram()
                return GenerationResult(
                    success=False,
                    error=(
                        "CUDA out of memory. Try: "
                        "device=cpu, smaller chunk_max_chars, "
                        "or conservative VRAM strategy."
                    ),
                )

            return GenerationResult(
                success=False,
                error=f"XTTS error: {type(exc).__name__}: {msg}",
            )

    # ── Voice listing / connection test ──────────────────

    async def list_voices(self, language: str | None = None) -> list[dict[str, str]]:
        """
        XTTS clones from reference audio — no preset voices.

        Returns the list of supported languages instead.
        """
        if language:
            return [
                lang for lang in _SUPPORTED_LANGUAGES if lang["id"].startswith(language)
            ]
        return list(_SUPPORTED_LANGUAGES)

    async def test_connection(self) -> bool:
        """Check that coqui-tts is importable and device is viable."""
        try:
            from TTS.api import TTS  # noqa: F401

            if self.device == "cuda":
                import torch

                if not torch.cuda.is_available():
                    logger.warning("XTTS: CUDA requested but unavailable.")
                    # Still True — engine can fall back to CPU.
            return True
        except ImportError:
            return False


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────


def _map_language(lang: str) -> str:
    """Normalise project language tags to XTTS codes."""
    _MAP = {
        "ar": "ar",
        "ar-SA": "ar",
        "ar-EG": "ar",
        "ar-AE": "ar",
        "en": "en",
        "en-US": "en",
        "en-GB": "en",
    }
    if lang in _MAP:
        return _MAP[lang]
    # Strip region: "fr-FR" → "fr"
    return lang.split("-")[0]


def _get_duration(path: Path) -> float:
    """Audio duration in seconds via pydub."""
    try:
        from pydub import AudioSegment

        return len(AudioSegment.from_file(str(path))) / 1000.0
    except Exception:
        return 0.0
