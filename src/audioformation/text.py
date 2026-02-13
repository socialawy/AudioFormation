"""
Text utilities — chunking, speaker tag parsing, language splitting.

Phase 1: breath-group chunking, basic sentence splitting.
Phase 2: multi-speaker tag parsing, language boundary detection.
"""

import re
from dataclasses import dataclass, field
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

# Speaker tag at start of line: [character_id]
_SPEAKER_TAG_RE = re.compile(r'^$$([a-zA-Z0-9_-]+)$$\s*', re.MULTILINE)


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
    # First split into sentences
    sentences = split_sentences(text)

    groups: list[str] = []
    for sentence in sentences:
        # Try splitting at breath points within the sentence
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

    # Step 1: Get initial units based on strategy
    if strategy == "breath_group":
        units = split_breath_groups(text)
    elif strategy == "sentence":
        units = split_sentences(text)
    else:
        # Fixed: hard split
        return _hard_split(text, max_chars)

    # Step 2: Merge small units, split large ones
    chunks: list[str] = []
    current = ""

    for unit in units:
        # If unit itself exceeds max_chars, hard-split it
        if len(unit) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split(unit, max_chars))
            continue

        # Try to append to current chunk
        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        else:
            # Current chunk is full — flush and start new
            if current:
                chunks.append(current.strip())
            current = unit

    # Flush remaining
    if current.strip():
        chunks.append(current.strip())

    return chunks


def _hard_split(text: str, max_chars: int) -> list[str]:
    """
    Hard split text at max_chars, preferring word boundaries.

    Used as fallback when no natural break points exist.
    """
    chunks: list[str] = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Find last space within max_chars
        split_pos = remaining[:max_chars].rfind(" ")
        if split_pos <= 0:
            # No space found — hard break
            split_pos = max_chars

        chunks.append(remaining[:split_pos].strip())
        remaining = remaining[split_pos:].strip()

    return chunks


# ──────────────────────────────────────────────
# Speaker tag parsing (Phase 1: parse but don't split)
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
        # Strip all speaker tags, return as single segment
        cleaned = _SPEAKER_TAG_RE.sub("", text).strip()
        return [Segment(character=default_character, text=cleaned, index=0)]

    # Multi-speaker parsing
    segments: list[Segment] = []
    current_character = default_character
    current_text_parts: list[str] = []
    index = 0

    for line in text.split("\n"):
        # Blank line → flush current segment, revert to default
        if not line.strip():
            if current_text_parts:
                segments.append(Segment(
                    character=current_character,
                    text=" ".join(current_text_parts).strip(),
                    index=index,
                ))
                index += 1
                current_text_parts = []
            current_character = default_character
            continue

        # Check for speaker tag
        tag_match = _SPEAKER_TAG_RE.match(line)
        if tag_match:
            # Flush previous segment if speaker changes
            new_char = tag_match.group(1)
            if current_text_parts and new_char != current_character:
                segments.append(Segment(
                    character=current_character,
                    text=" ".join(current_text_parts).strip(),
                    index=index,
                ))
                index += 1
                current_text_parts = []

            current_character = new_char
            # Get text after the tag
            remaining = line[tag_match.end():].strip()
            if remaining:
                current_text_parts.append(remaining)
        else:
            current_text_parts.append(line.strip())

    # Flush final segment
    if current_text_parts:
        segments.append(Segment(
            character=current_character,
            text=" ".join(current_text_parts).strip(),
            index=index,
        ))

    return segments


def validate_speaker_tags(
    text: str,
    known_characters: set[str],
) -> list[str]:
    """
    Check that all [speaker_id] tags in text reference known characters.

    Returns list of warning strings for unknown characters.
    """
    warnings: list[str] = []
    for match in _SPEAKER_TAG_RE.finditer(text):
        char_id = match.group(1)
        if char_id not in known_characters:
            warnings.append(
                f"Line {text[:match.start()].count(chr(10)) + 1}: "
                f"Unknown speaker tag [{char_id}]."
            )
    return warnings