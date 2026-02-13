"""Tests for TTS engine interface, registry, and edge-tts SSML mapping."""

import pytest

from audioformation.engines.base import GenerationRequest, GenerationResult
from audioformation.engines.registry import registry
from audioformation.engines.edge_tts import (
    direction_to_ssml,
    _process_inline_markers,
)
from pathlib import Path


class TestEngineRegistry:
    """Tests for the engine registry."""

    def test_edge_registered(self) -> None:
        assert registry.is_registered("edge")

    def test_list_available(self) -> None:
        available = registry.list_available()
        assert "edge" in available

    def test_get_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent_engine")

    def test_get_returns_engine(self) -> None:
        engine = registry.get("edge")
        assert engine.name == "edge"
        assert engine.supports_ssml is True
        assert engine.supports_cloning is False
        assert engine.requires_gpu is False

    def test_get_caches_instance(self) -> None:
        engine1 = registry.get("edge")
        engine2 = registry.get("edge")
        assert engine1 is engine2


class TestGenerationRequest:
    """Tests for the generation request data class."""

    def test_minimal_request(self) -> None:
        req = GenerationRequest(
            text="Hello world",
            output_path=Path("/tmp/test.mp3"),
        )
        assert req.text == "Hello world"
        assert req.voice is None
        assert req.language == "ar"

    def test_full_request(self) -> None:
        req = GenerationRequest(
            text="مرحبا",
            output_path=Path("/tmp/test.mp3"),
            voice="ar-SA-HamedNeural",
            language="ar",
            reference_audio=Path("/tmp/ref.wav"),
            direction={"pace": "slow", "energy": "quiet", "emotion": "wonder"},
            params={"ssml": True},
        )
        assert req.voice == "ar-SA-HamedNeural"
        assert req.direction["pace"] == "slow"


class TestDirectionToSSML:
    """Tests for SSML direction mapping."""

    def test_plain_text_no_direction(self) -> None:
        result = direction_to_ssml("Hello", {})
        assert "<speak>" in result
        assert "Hello" in result
        # No prosody wrapper if no direction attributes apply
        assert "prosody" not in result

    def test_pace_mapping(self) -> None:
        result = direction_to_ssml("Hello", {"pace": "slow"})
        assert 'rate="slow"' in result
        assert "<prosody" in result

    def test_energy_mapping(self) -> None:
        result = direction_to_ssml("Hello", {"energy": "whisper"})
        assert 'volume="x-soft"' in result

    def test_emotion_mapping(self) -> None:
        result = direction_to_ssml("Hello", {"emotion": "wonder"})
        assert 'pitch="+5%"' in result

    def test_combined_direction(self) -> None:
        result = direction_to_ssml("Hello", {
            "pace": "slow",
            "energy": "quiet",
            "emotion": "sadness",
        })
        assert 'rate="slow"' in result
        assert 'volume="soft"' in result
        assert 'pitch="-5%"' in result

    def test_moderate_pace_omitted(self) -> None:
        result = direction_to_ssml("Hello", {"pace": "moderate"})
        # "medium" maps but should not add prosody since it's the default
        assert "prosody" not in result

    def test_normal_energy_omitted(self) -> None:
        result = direction_to_ssml("Hello", {"energy": "normal"})
        assert "prosody" not in result

    def test_unknown_values_ignored(self) -> None:
        result = direction_to_ssml("Hello", {
            "pace": "unknown_pace",
            "emotion": "unknown_emotion",
        })
        # Unknown values produce no attributes → no prosody tag
        assert "prosody" not in result

    def test_quiet_contemplation_maps(self) -> None:
        result = direction_to_ssml("Hello", {"energy": "quiet contemplation"})
        assert 'volume="soft"' in result

    def test_arabic_text_preserved(self) -> None:
        result = direction_to_ssml("بسم الله الرحمن الرحيم", {"pace": "slow"})
        assert "بسم الله" in result


class TestInlineMarkers:
    """Tests for inline SSML break insertion."""

    def test_ellipsis(self) -> None:
        result = _process_inline_markers("Wait... then continue")
        assert 'break time="400ms"' in result

    def test_unicode_ellipsis(self) -> None:
        result = _process_inline_markers("Wait\u2026 then continue")
        assert 'break time="400ms"' in result

    def test_em_dash(self) -> None:
        result = _process_inline_markers("He said — nothing")
        assert 'break time="250ms"' in result

    def test_paragraph_break(self) -> None:
        result = _process_inline_markers("End of paragraph.\n\nStart of next.")
        assert 'break time="600ms"' in result

    def test_no_markers(self) -> None:
        text = "Plain text without markers."
        assert _process_inline_markers(text) == text