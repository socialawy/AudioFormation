"""Tests for Arabic text processing — diacritics, language detection, dialect matching."""

import pytest

from audioformation.utils.arabic import (
    detect_diacritization_level,
    classify_diacritization,
    is_arabic,
    is_latin,
    detect_language_segments,
    validate_dialect_voice_match,
    _classify_word,
)


class TestDiacritizationDetection:
    """Tests for diacritization level measurement."""

    def test_undiacritized_text(self) -> None:
        text = "بسم الله الرحمن الرحيم"
        level = detect_diacritization_level(text)
        assert level < 0.05
        assert classify_diacritization(text) == "undiacritized"

    def test_diacritized_text(self) -> None:
        text = "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ"
        level = detect_diacritization_level(text)
        assert level > 0.30
        assert classify_diacritization(text) == "diacritized"

    def test_partial_diacritization(self) -> None:
        text = "بِسم الله الرَّحمن الرحيم"
        level = detect_diacritization_level(text)
        assert 0.05 <= level <= 0.30
        assert classify_diacritization(text) == "partial"

    def test_non_arabic_returns_zero(self) -> None:
        text = "Hello world, this is English."
        level = detect_diacritization_level(text)
        assert level == 0.0

    def test_empty_text(self) -> None:
        assert detect_diacritization_level("") == 0.0
        assert detect_diacritization_level("   ") == 0.0

    def test_numbers_only(self) -> None:
        assert detect_diacritization_level("12345") == 0.0


class TestLanguageDetection:
    """Tests for Arabic vs Latin detection."""

    def test_arabic_text(self) -> None:
        assert is_arabic("بسم الله الرحمن الرحيم") is True

    def test_english_text(self) -> None:
        assert is_arabic("Hello world") is False
        assert is_latin("Hello world") is True

    def test_latin_is_not_arabic(self) -> None:
        assert is_latin("بسم الله") is False

    def test_empty_text(self) -> None:
        assert is_arabic("") is False
        assert is_latin("") is False


class TestWordClassification:
    """Tests for per-word language classification."""

    def test_arabic_word(self) -> None:
        assert _classify_word("الله") == "ar"

    def test_english_word(self) -> None:
        assert _classify_word("Hello") == "en"

    def test_number_is_mixed(self) -> None:
        assert _classify_word("2026") == "mixed"

    def test_punctuation_is_mixed(self) -> None:
        assert _classify_word("...") == "mixed"


class TestLanguageSegments:
    """Tests for mixed-language segment detection."""

    def test_pure_arabic(self) -> None:
        text = "بسم الله الرحمن الرحيم"
        segments = detect_language_segments(text)
        assert len(segments) == 1
        assert segments[0].language == "ar"

    def test_pure_english(self) -> None:
        text = "Hello world from here"
        segments = detect_language_segments(text)
        assert len(segments) == 1
        assert segments[0].language == "en"

    def test_mixed_arabic_english(self) -> None:
        text = "ذهب إلى Microsoft لحضور الاجتماع"
        segments = detect_language_segments(text)
        assert len(segments) >= 2
        # Should have Arabic, then English, then Arabic
        languages = [s.language for s in segments]
        assert "ar" in languages
        assert "en" in languages

    def test_empty_text(self) -> None:
        assert detect_language_segments("") == []
        assert detect_language_segments("   ") == []

    def test_segment_positions(self) -> None:
        text = "مرحبا Hello عالم"
        segments = detect_language_segments(text)
        assert len(segments) == 3
        assert segments[0].language == "ar"
        assert segments[1].language == "en"
        assert segments[2].language == "ar"


class TestDialectVoiceMatching:
    """Tests for dialect-voice compatibility checking."""

    def test_matching_dialect_voice(self) -> None:
        result = validate_dialect_voice_match("msa", "ar-SA-HamedNeural")
        assert result is None  # No warning

    def test_mismatched_dialect_voice(self) -> None:
        result = validate_dialect_voice_match("eg", "ar-SA-HamedNeural")
        assert result is not None
        assert "eg" in result
        assert "ar-SA" in result

    def test_none_dialect_no_warning(self) -> None:
        assert validate_dialect_voice_match(None, "ar-SA-HamedNeural") is None

    def test_none_voice_no_warning(self) -> None:
        assert validate_dialect_voice_match("msa", None) is None

    def test_unknown_dialect_no_warning(self) -> None:
        assert validate_dialect_voice_match("unknown", "ar-SA-HamedNeural") is None

    def test_egyptian_voice_matches_eg(self) -> None:
        result = validate_dialect_voice_match("eg", "ar-EG-SalmaNeural")
        assert result is None