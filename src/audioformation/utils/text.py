"""
Text utilities — chunking, speaker tag parsing, language splitting.

Phase 1: breath-group chunking, basic sentence splitting.
Phase 2: multi-speaker tag parsing, language boundary detection.
"""

import re
from dataclasses import dataclass
from typing import Literal

# ──────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────


@dataclass
class Segment:
    """A contiguous block of text spoken by one character."""

    character: str
    text: str
    index: int


@dataclass
class Chunk:
    """A generation-sized piece of text within a segment."""

    text: str
    segment_index: int
    chunk_index: int
    character: str
    language: str = ""


# ──────────────────────────────────────────────
# Sentence splitting
# ──────────────────────────────────────────────

# Arabic sentence terminators + standard Latin ones
_SENTENCE_RE = re.compile(
    r'(?<=[.!?؟。])\s+'  # Split after sentence-ending punctuation + whitespace
)

# Arabic comma and semicolon for breath-group splitting
_BREATH_RE = re.compile(
    r'(?<=[,،;؛:])\s+'  # Split after clause-level punctuation + whitespace
)


def _is_speaker_tag(line: str) -> tuple[bool, str, str]:
    """
    Check if a line starts with a speaker tag like [character_id].

    Returns (is_tag, character_id, remaining_text).
    If not a tag, returns (False, "", original_line).

    Using explicit parsing instead of regex to avoid platform-specific
    regex edge cases with ^ anchors and bracket escaping.
    """
    stripped = line.strip()
    if not stripped.startswith("["):
        return False, "", stripped

    close = stripped.find("]")
    if close == -1:
        return False, "", stripped

    tag_content = stripped[1:close]

    # Validate tag content: alphanumeric + underscore + hyphen only
    if not tag_content:
        return False, "", stripped
    if not all(c.isalnum() or c in ("_", "-") for c in tag_content):
        return False, "", stripped

    remaining = stripped[close + 1:].strip()
    return True, tag_content, remaining


def _find_all_speaker_tags(text: str) -> list[tuple[int, str]]:
    """
    Find all speaker tags in text with their line numbers.

    Returns list of (line_number, character_id) tuples.
    Uses explicit parsing, not regex.
    """
    tags = []
    for i, line in enumerate(text.split("\n")):
        is_tag, char_id, _ = _is_speaker_tag(line)
        if is_tag:
            tags.append((i, char_id))
    return tags


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using Arabic and Latin punctuation.

    Returns list of stripped, non-empty sentences.
    """
    sentences = _SENTENCE_RE.split(text.strip())
    return [s.strip() for s in sentences if s.strip()]


def split_breath_groups(text: str) -> list[str]:
    """
    Split text into breath groups — sub-sentence units at clause boundaries.

    Splits on commas, semicolons, colons (Arabic + Latin), then falls back
    to sentence splitting for runs without clause punctuation.
    """
    sentences = split_sentences(text)

    groups: list[str] = []
    for sentence in sentences:
        parts = _BREATH_RE.split(sentence)
        for part in parts:
            stripped = part.strip()
            if stripped:
                groups.append(stripped)

    return groups


def chunk_text(
    text: str,
    max_chars: int = 200,
    strategy: Literal["breath_group", "sentence", "fixed"] = "breath_group",
) -> list[str]:
    """
    Split text into generation-ready chunks respecting max_chars.

    Strategies:
    - breath_group: Split at clause boundaries, merge small fragments.
    - sentence: Split at sentence boundaries only.
    - fixed: Hard split at max_chars (last resort).

    Returns list of non-empty chunks, each <= max_chars.
    """
    if not text.strip():
        return []

    if strategy == "breath_group":
        units = split_breath_groups(text)
    elif strategy == "sentence":
        units = split_sentences(text)
    else:
        return _hard_split(text, max_chars)

    # Merge small units, split large ones
    chunks: list[str] = []
    current = ""

    for unit in units:
        if len(unit) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split(unit, max_chars))
            continue

        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = unit

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _hard_split(text: str, max_chars: int) -> list[str]:
    """
    Hard split text at max_chars, preferring word boundaries.
    """
    chunks: list[str] = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        split_pos = remaining[:max_chars].rfind(" ")
        if split_pos <= 0:
            split_pos = max_chars

        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()

    return chunks


# ──────────────────────────────────────────────
# Speaker tag parsing
# ──────────────────────────────────────────────


def parse_chapter_segments(
    text: str,
    mode: Literal["single", "multi"] = "single",
    default_character: str = "narrator",
) -> list[Segment]:
    """
    Parse a chapter text into speaker-attributed segments.

    Phase 1 (mode="single"): Returns one segment with all text,
    speaker tags stripped.

    Phase 2 (mode="multi"): Splits text at [speaker_id] tags,
    tracks speaker changes, reverts to default on blank lines.
    """
    if mode == "single":
        cleaned = _strip_all_tags(text)
        return [Segment(character=default_character, text=cleaned, index=0)]

    # Multi-speaker parsing
    segments: list[Segment] = []
    current_character = default_character
    current_text_parts: list[str] = []
    index = 0

    def flush() -> None:
        """Flush accumulated text into a segment."""
        nonlocal index
        combined = " ".join(current_text_parts).strip()
        if combined:
            segments.append(Segment(
                character=current_character,
                text=combined,
                index=index,
            ))
            index += 1

    for line in text.split("\n"):
        # Blank line → flush current segment, revert to default
        if not line.strip():
            flush()
            current_text_parts = []
            current_character = default_character
            continue

        # Check for speaker tag
        is_tag, tag_char, remaining = _is_speaker_tag(line)

        if is_tag:
            # Speaker change — flush previous segment if different speaker
            if tag_char != current_character and current_text_parts:
                flush()
                current_text_parts = []

            current_character = tag_char
            if remaining:
                current_text_parts.append(remaining)
        else:
            current_text_parts.append(line.strip())

    # Flush final segment
    flush()

    return segments


def _strip_all_tags(text: str) -> str:
    """
    Remove all [speaker_id] tags from text, preserving the rest.

    Used in single-narrator mode.
    """
    lines = []
    for line in text.split("\n"):
        is_tag, _, remaining = _is_speaker_tag(line)
        if is_tag:
            # Keep the remaining text after the tag
            if remaining:
                lines.append(remaining)
        else:
            lines.append(line)

    return " ".join(lines).strip()


def validate_speaker_tags(
    text: str,
    known_characters: set[str],
) -> list[str]:
    """
    Check that all [speaker_id] tags in text reference known characters.

    Returns list of warning strings for unknown characters.
    """
    warnings: list[str] = []
    for line_num, line in enumerate(text.split("\n"), start=1):
        is_tag, char_id, _ = _is_speaker_tag(line)
        if is_tag and char_id not in known_characters:
            warnings.append(
                f"Line {line_num}: Unknown speaker tag [{char_id}]."
            )
    return warnings