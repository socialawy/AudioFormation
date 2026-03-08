"""Tests for TTS engine interface, registry, and edge-tts direction mapping."""

import pytest

from audioformation.engines.base import GenerationRequest
from audioformation.engines.registry import registry
from audioformation.engines.edge_tts import (
    _direction_to_params,
    _process_inline_markers_plain,
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


class TestDirectionToParams:
    """Tests for edge-tts native direction param mapping."""

    def test_empty_direction(self) -> None:
        rate, volume, pitch = _direction_to_params({})
        assert rate == "+0%"
        assert volume == "+0%"
        assert pitch == "+0Hz"

    def test_pace_mapping(self) -> None:
        rate, _, _ = _direction_to_params({"pace": "slow"})
        assert rate == "-25%"

    def test_energy_mapping(self) -> None:
        _, volume, _ = _direction_to_params({"energy": "whisper"})
        assert volume == "-80%"

    def test_emotion_mapping(self) -> None:
        _, _, pitch = _direction_to_params({"emotion": "wonder"})
        assert pitch == "+10Hz"

    def test_combined_direction(self) -> None:
        rate, volume, pitch = _direction_to_params(
            {
                "pace": "slow",
                "energy": "quiet",
                "emotion": "sadness",
            },
        )
        assert rate == "-25%"
        assert volume == "-40%"
        assert pitch == "-10Hz"

    def test_moderate_pace_is_default(self) -> None:
        rate, _, _ = _direction_to_params({"pace": "moderate"})
        assert rate == "+0%"

    def test_normal_energy_is_default(self) -> None:
        _, volume, _ = _direction_to_params({"energy": "normal"})
        assert volume == "+0%"

    def test_unknown_values_use_defaults(self) -> None:
        rate, volume, pitch = _direction_to_params(
            {
                "pace": "unknown_pace",
                "emotion": "unknown_emotion",
            },
        )
        assert rate == "+0%"
        assert volume == "+0%"
        assert pitch == "+0Hz"

    def test_quiet_contemplation_maps(self) -> None:
        _, volume, _ = _direction_to_params({"energy": "quiet contemplation"})
        assert volume == "-30%"

    def test_calm_energy_maps(self) -> None:
        _, volume, _ = _direction_to_params({"energy": "calm"})
        assert volume == "-15%"

    def test_contemplative_emotion_maps(self) -> None:
        _, _, pitch = _direction_to_params({"emotion": "contemplative"})
        assert pitch == "-5Hz"


class TestInlineMarkers:
    """Tests for inline marker normalization for plain-text TTS."""

    def test_ellipsis_preserved(self) -> None:
        result = _process_inline_markers_plain("Wait... then continue")
        assert "..." in result

    def test_unicode_ellipsis_normalized(self) -> None:
        result = _process_inline_markers_plain("Wait\u2026 then continue")
        assert "..." in result
        assert "\u2026" not in result

    def test_em_dash_to_comma(self) -> None:
        result = _process_inline_markers_plain("He said \u2014 nothing")
        assert "\u2014" not in result
        assert ", " in result

    def test_en_dash_to_comma(self) -> None:
        result = _process_inline_markers_plain("pages 1\u2013 5")
        assert "\u2013" not in result

    def test_no_markers(self) -> None:
        text = "Plain text without markers."
        assert _process_inline_markers_plain(text) == text
