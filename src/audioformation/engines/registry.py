"""
Engine discovery and registration.
"""

from typing import Any

from audioformation.engines.base import TTSEngine


class EngineRegistry:
    """Registry of available TTS engines."""

    def __init__(self) -> None:
        self._engines: dict[str, TTSEngine] = {}
        self._factories: dict[str, type] = {}

    def register(self, name: str, engine_class: type) -> None:
        """Register an engine class by name (lazy — not instantiated yet)."""
        self._factories[name] = engine_class

    def get(self, name: str, **kwargs: Any) -> TTSEngine:
        """Get an engine instance by name. Instantiates on first call, caches."""
        if name in self._engines:
            return self._engines[name]

        if name not in self._factories:
            available = ", ".join(sorted(self._factories.keys()))
            raise KeyError(
                f"Engine '{name}' not registered. Available: {available}"
            )

        engine = self._factories[name](**kwargs)
        self._engines[name] = engine
        return engine

    def list_available(self) -> list[str]:
        """Return names of all registered engines."""
        return sorted(self._factories.keys())

    def is_registered(self, name: str) -> bool:
        """Check if an engine is registered."""
        return name in self._factories


# Global registry instance
registry = EngineRegistry()


def _register_defaults() -> None:
    """Register all built-in engines."""
    from audioformation.engines.edge_tts import EdgeTTSEngine
    registry.register("edge", EdgeTTSEngine)

    # gTTS fallback — always available if pip install gTTS
    try:
        from audioformation.engines.gtts_engine import GTTSEngine
        registry.register("gtts", GTTSEngine)
    except ImportError:
        pass

    # XTTS registered only if coqui-tts is installed
    try:
        from audioformation.engines.xtts import XTTSEngine
        registry.register("xtts", XTTSEngine)
    except ImportError:
        pass

    # ElevenLabs registered only if httpx is installed
    try:
        from audioformation.engines.elevenlabs import ElevenLabsEngine
        registry.register("elevenlabs", ElevenLabsEngine)
    except ImportError:
        pass


_register_defaults()
