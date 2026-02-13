"""Tests for text chunking, sentence splitting, and speaker tag parsing."""

import pytest

from audioformation.utils.text import (
    split_sentences,
    split_breath_groups,
    chunk_text,
    parse_chapter_segments,
    validate_speaker_tags,
)


class TestSplitSentences:
    """Tests for sentence-level splitting."""

    def test_english_sentences(self) -> None:
        text = "Hello world. This is a test. Another sentence!"
        result = split_sentences(text)
        assert result == ["Hello world.", "This is a test.", "Another sentence!"]

    def test_arabic_sentences(self) -> None:
        text = "بسم الله الرحمن الرحيم. هذا اختبار. جملة أخرى؟"
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0] == "بسم الله الرحمن الرحيم."
        assert result[2] == "جملة أخرى؟"

    def test_single_sentence(self) -> None:
        result = split_sentences("Just one sentence.")
        assert result == ["Just one sentence."]

    def test_empty_text(self) -> None:
        assert split_sentences("") == []
        assert split_sentences("   ") == []


class TestSplitBreathGroups:
    """Tests for clause-level splitting."""

    def test_comma_split(self) -> None:
        text = "First clause, second clause, third clause."
        result = split_breath_groups(text)
        assert len(result) == 3

    def test_arabic_comma(self) -> None:
        text = "الجزء الأول، الجزء الثاني، الجزء الثالث."
        result = split_breath_groups(text)
        assert len(result) == 3

    def test_semicolon_split(self) -> None:
        text = "Part one; part two; part three."
        result = split_breath_groups(text)
        assert len(result) == 3

    def test_no_clause_markers(self) -> None:
        text = "A simple sentence without any clause markers."
        result = split_breath_groups(text)
        assert len(result) == 1


class TestChunkText:
    """Tests for generation-ready chunking."""

    def test_short_text_single_chunk(self) -> None:
        text = "Short text."
        result = chunk_text(text, max_chars=200)
        assert result == ["Short text."]

    def test_respects_max_chars(self) -> None:
        text = "This is sentence one. This is sentence two. This is sentence three."
        result = chunk_text(text, max_chars=50)
        for chunk in result:
            assert len(chunk) <= 50

    def test_arabic_chunking(self) -> None:
        text = (
            "بسم الله الرحمن الرحيم. "
            "في البدء كان الكلمة، والكلمة كانت عند الله. "
            "هذا نص طويل لاختبار التقطيع."
        )
        result = chunk_text(text, max_chars=80)
        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 80

    def test_sentence_strategy(self) -> None:
        text = "First. Second. Third."
        result = chunk_text(text, max_chars=200, strategy="sentence")
        # All sentences fit in one chunk
        assert len(result) == 1

    def test_fixed_strategy(self) -> None:
        text = "A" * 500
        result = chunk_text(text, max_chars=200, strategy="fixed")
        assert len(result) == 3
        assert all(len(c) <= 200 for c in result)

    def test_empty_text_returns_empty(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_merges_small_fragments(self) -> None:
        text = "A, B, C, D, E."
        result = chunk_text(text, max_chars=200)
        # Small fragments should be merged into fewer chunks
        assert len(result) <= 2

    def test_long_word_hard_split(self) -> None:
        text = "X" * 300
        result = chunk_text(text, max_chars=200)
        assert len(result) == 2
        assert all(len(c) <= 200 for c in result)


class TestParseChapterSegments:
    """Tests for speaker tag parsing."""

    def test_single_mode_strips_tags(self) -> None:
        text = "[hero] Some dialogue.\nNarration continues."
        segments = parse_chapter_segments(text, mode="single", default_character="narrator")
        assert len(segments) == 1
        assert segments[0].character == "narrator"
        assert "Some dialogue" in segments[0].text
        assert "[hero]" not in segments[0].text

    def test_multi_mode_splits_speakers(self) -> None:
        text = (
            "The narrator speaks here.\n"
            "\n"
            "[hero] I will not surrender!\n"
            "\n"
            "[villain] We shall see.\n"
            "\n"
            "Silence returned."
        )
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 4
        assert segments[0].character == "narrator"
        assert segments[1].character == "hero"
        assert segments[2].character == "villain"
        assert segments[3].character == "narrator"

    def test_multi_mode_default_on_blank_line(self) -> None:
        text = "[hero] First line.\n\nSecond line by default."
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert segments[0].character == "hero"
        assert segments[1].character == "narrator"

    def test_multi_mode_consecutive_same_speaker(self) -> None:
        text = "[hero] Line one.\n[hero] Line two."
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        # Same speaker, no blank line between — should be one segment
        assert len(segments) == 1
        assert "Line one" in segments[0].text
        assert "Line two" in segments[0].text

    def test_arabic_speaker_tags(self) -> None:
        text = (
            "قال الراوي بصوت هادئ.\n"
            "\n"
            "[hero] لن أستسلم أبداً.\n"
            "\n"
            "عاد الصمت."
        )
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 3
        assert segments[1].character == "hero"
        assert "لن أستسلم" in segments[1].text


class TestValidateSpeakerTags:
    """Tests for speaker tag validation."""

    def test_valid_tags_no_warnings(self) -> None:
        text = "[hero] Hello.\n[villain] Goodbye."
        warnings = validate_speaker_tags(text, {"hero", "villain"})
        assert warnings == []

    def test_unknown_tag_warns(self) -> None:
        text = "[unknown_char] Some text."
        warnings = validate_speaker_tags(text, {"hero", "villain"})
        assert len(warnings) == 1
        assert "unknown_char" in warnings[0]

    def test_no_tags_no_warnings(self) -> None:
        text = "Plain text without any tags."
        warnings = validate_speaker_tags(text, {"hero"})
        assert warnings == []


class TestSpeakerTagParser:
    """Direct tests for the _is_speaker_tag helper."""

    def test_simple_tag(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, char_id, remaining = _is_speaker_tag("[hero] Some text.")
        assert is_tag is True
        assert char_id == "hero"
        assert remaining == "Some text."

    def test_tag_no_text(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, char_id, remaining = _is_speaker_tag("[villain]")
        assert is_tag is True
        assert char_id == "villain"
        assert remaining == ""

    def test_no_tag(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, char_id, remaining = _is_speaker_tag("Plain text here.")
        assert is_tag is False
        assert remaining == "Plain text here."

    def test_tag_with_underscore(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, char_id, remaining = _is_speaker_tag("[old_man] Hello.")
        assert is_tag is True
        assert char_id == "old_man"

    def test_tag_with_hyphen(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, char_id, remaining = _is_speaker_tag("[char-1] Hello.")
        assert is_tag is True
        assert char_id == "char-1"

    def test_bracket_in_text_not_tag(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        # Brackets mid-text are not tags
        is_tag, _, _ = _is_speaker_tag("He said [something] loud.")
        assert is_tag is False

    def test_empty_brackets_not_tag(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, _, _ = _is_speaker_tag("[] nothing")
        assert is_tag is False

    def test_arabic_text_after_tag(self) -> None:
        from audioformation.utils.text import _is_speaker_tag

        is_tag, char_id, remaining = _is_speaker_tag("[hero] لن أستسلم أبداً.")
        assert is_tag is True
        assert char_id == "hero"
        assert "لن أستسلم" in remaining