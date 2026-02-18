"""
Engine discovery and registration.
"""

from typing import Any, Callable
from audioformation.engines.base import TTSEngine


class EngineRegistry:
    """Registry for TTS engines with lazy loading and capability checking."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], TTSEngine]] = {}
        self._engines: dict[str, TTSEngine] = {}

    def register(self, name: str, factory: Callable[[], TTSEngine]) -> None:
        """Register an engine factory."""
        self._factories[name] = factory

    def get(self, name: str, **kwargs: Any) -> TTSEngine:
        """Get an engine instance by name. Instantiates on first call, caches."""
        if name in self._engines:
            return self._engines[name]

        if name not in self._factories:
            available = ", ".join(sorted(self._factories.keys()))
            raise KeyError(f"Engine '{name}' not registered. Available: {available}")

        engine = self._factories[name](**kwargs)
        self._engines[name] = engine
        return engine

    def get_capabilities(self, name: str) -> dict[str, Any]:
        """Get engine capabilities without instantiation."""
        if name not in self._factories:
            available = ", ".join(sorted(self._factories.keys()))
            raise KeyError(f"Engine '{name}' not registered. Available: {available}")

        # Create a temporary instance to get capabilities
        try:
            engine = self._factories[name]()
            return {
                "supports_cloning": engine.supports_cloning,
                "supports_ssml": engine.supports_ssml,
                "requires_gpu": engine.requires_gpu,
                "requires_api_key": engine.requires_api_key,
                "api_key_name": engine.api_key_name,
            }
        except Exception as e:
            # Handle engines that require configuration (e.g., API keys)
            if "API key" in str(e):
                # Return default capabilities for engines that need API keys
                return {
                    "supports_cloning": True,  # Assume based on engine type
                    "supports_ssml": False,
                    "requires_gpu": False,
                    "requires_api_key": True,
                    "api_key_name": f"{name.upper()}_API_KEY",
                    "error": "API key required",
                }
            raise

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
