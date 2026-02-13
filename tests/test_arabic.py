"""Tests for Arabic text processing — diacritics, language detection, dialect matching."""

import pytest
from pathlib import Path

from audioformation.utils.arabic import (
    detect_diacritization_level,
    classify_diacritization,
    detect_language,
    detect_language_segments,
    split_at_language_boundaries,
    validate_dialect_voice_match,
    auto_diacritize,
    diacritize_file,
    is_arabic_char,
    is_latin_char,
    is_diacritic,
)


class TestCharacterDetection:
    """Tests for character-level classification."""

    def test_arabic_char(self) -> None:
        assert is_arabic_char("ا") is True
        assert is_arabic_char("م") is True

    def test_latin_char(self) -> None:
        assert is_latin_char("A") is True
        assert is_latin_char("z") is True

    def test_arabic_not_latin(self) -> None:
        assert is_latin_char("ا") is False

    def test_latin_not_arabic(self) -> None:
        assert is_arabic_char("A") is False

    def test_diacritic_detection(self) -> None:
        assert is_diacritic("\u064E") is True   # fatha
        assert is_diacritic("\u0651") is True   # shadda
        assert is_diacritic("ا") is False        # alef is not a diacritic
        assert is_diacritic("A") is False

    def test_digit_is_neither(self) -> None:
        assert is_arabic_char("5") is False
        assert is_latin_char("5") is False


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
    """Tests for text-level language detection."""

    def test_arabic_text(self) -> None:
        assert detect_language("بسم الله الرحمن الرحيم") == "ar"

    def test_english_text(self) -> None:
        assert detect_language("Hello world this is English") == "en"

    def test_mixed_defaults_to_arabic(self) -> None:
        # Arabic characters > 30% of total → "ar"
        assert detect_language("مرحبا Hello") == "ar"

    def test_empty_defaults_to_arabic(self) -> None:
        assert detect_language("") == "ar"
        assert detect_language("12345") == "ar"


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

    def test_short_inline_english_absorbed(self) -> None:
        # "Microsoft" is 1 word — should be absorbed into Arabic
        text = "ذهب إلى Microsoft لحضور الاجتماع"
        segments = detect_language_segments(text)
        # Short inline gets absorbed, so might be 1 segment
        assert len(segments) >= 1
        assert segments[0].language == "ar"

    def test_long_english_creates_separate_segment(self) -> None:
        # Enough English words to trigger a genuine switch
        text = "مرحبا The quick brown fox jumps over the lazy dog عالم"
        segments = detect_language_segments(text)
        assert len(segments) >= 2
        languages = [s.language for s in segments]
        assert "ar" in languages
        assert "en" in languages

    def test_empty_text(self) -> None:
        assert detect_language_segments("") == []
        assert detect_language_segments("   ") == []


class TestLanguageBoundarySplitting:
    """Tests for splitting at language boundaries with max_chars."""

    def test_short_text_single_segment(self) -> None:
        text = "مرحبا بالعالم"
        segments = split_at_language_boundaries(text, max_chars=200)
        assert len(segments) == 1

    def test_respects_max_chars(self) -> None:
        # Long Arabic text should be split
        text = "هذا نص طويل جداً " * 20  # ~360 chars
        segments = split_at_language_boundaries(text, max_chars=100)
        for seg in segments:
            assert len(seg.text) <= 150  # some tolerance for sentence boundaries


class TestDialectVoiceMatching:
    """Tests for dialect-voice compatibility checking."""

    def test_matching_dialect_voice(self) -> None:
        result = validate_dialect_voice_match("msa", "ar-SA-HamedNeural")
        assert result is None

    def test_mismatched_dialect_voice(self) -> None:
        result = validate_dialect_voice_match("eg", "ar-SA-HamedNeural")
        assert result is not None
        assert "eg" in result.lower() or "ar-SA" in result

    def test_none_dialect_no_warning(self) -> None:
        assert validate_dialect_voice_match(None, "ar-SA-HamedNeural") is None

    def test_none_voice_no_warning(self) -> None:
        assert validate_dialect_voice_match("msa", None) is None

    def test_unknown_dialect_warns(self) -> None:
        result = validate_dialect_voice_match("unknown", "ar-SA-HamedNeural")
        assert result is not None  # Unknown dialect produces a warning

    def test_egyptian_voice_matches_eg(self) -> None:
        result = validate_dialect_voice_match("eg", "ar-EG-SalmaNeural")
        assert result is None

    def test_saudi_voice_matches_sa(self) -> None:
        result = validate_dialect_voice_match("sa", "ar-SA-HamedNeural")
        assert result is None


class TestAutoDiacritize:
    """Tests for automatic diacritization via Mishkal."""

    def test_diacritizes_arabic_text(self) -> None:
        result = auto_diacritize("مرحبا بالعالم")
        assert result.level_after > result.level_before
        assert result.engine == "mishkal"
        assert len(result.diacritized) >= len(result.original)

    def test_preserves_already_diacritized(self) -> None:
        text = "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ"
        result = auto_diacritize(text)
        # Should still have high diacritization
        assert result.level_after > 0.25

    def test_result_has_before_after_levels(self) -> None:
        result = auto_diacritize("بسم الله الرحمن الرحيم")
        assert isinstance(result.level_before, float)
        assert isinstance(result.level_after, float)
        assert 0.0 <= result.level_before <= 1.0
        assert 0.0 <= result.level_after <= 1.0

    def test_unknown_engine_falls_back_to_mishkal(self) -> None:
        result = auto_diacritize("مرحبا", engine="nonexistent")
        assert len(result.warnings) >= 1
        assert result.diacritized  # Still produces output


class TestDiacritizeFile:
    """Tests for file-level diacritization."""

    def test_creates_diacritized_file(self, tmp_path) -> None:
        input_file = tmp_path / "ch01.txt"
        input_file.write_text("بسم الله الرحمن الرحيم", encoding="utf-8")

        result = diacritize_file(input_file)

        output_file = tmp_path / "ch01.diacritized.txt"
        assert output_file.exists()
        assert result.level_after > result.level_before

        content = output_file.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_custom_output_path(self, tmp_path) -> None:
        input_file = tmp_path / "ch01.txt"
        input_file.write_text("مرحبا بالعالم", encoding="utf-8")
        output_file = tmp_path / "custom_output.txt"

        diacritize_file(input_file, output_path=output_file)

        assert output_file.exists()

    def test_preserves_original_file(self, tmp_path) -> None:
        input_file = tmp_path / "ch01.txt"
        original_text = "بسم الله الرحمن الرحيم"
        input_file.write_text(original_text, encoding="utf-8")

        diacritize_file(input_file)

        # Original should be unchanged
        assert input_file.read_text(encoding="utf-8") == original_text