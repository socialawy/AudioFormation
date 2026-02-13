"""
Arabic text processing — diacritics detection, language segmentation,
dialect-voice matching.

Strategy:
1. Detect diacritization level (undiacritized / partial / diacritized)
2. Auto-diacritize via Mishkal when needed (optional dependency)
3. Detect Arabic vs Latin segments for mixed text
4. Validate dialect-voice pairing
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from audioformation.config import (
    DIACRITIZATION_UNDIACRITIZED,
    DIACRITIZATION_PARTIAL,
    DIALECT_VOICE_MAP,
)


# ──────────────────────────────────────────────
# Unicode ranges
# ──────────────────────────────────────────────

# Arabic diacritical marks (tashkeel)
_ARABIC_DIACRITICS = set(
    chr(c) for c in range(0x064B, 0x0653)  # Fathatan through Maddah
)
_ARABIC_DIACRITICS.add(chr(0x0670))  # Superscript Alef
_ARABIC_DIACRITICS.add(chr(0x0656))  # Subscript Alef
_ARABIC_DIACRITICS.add(chr(0x0657))  # Inverted Damma
_ARABIC_DIACRITICS.add(chr(0x0658))  # Mark Noon Ghunna

# Arabic letter ranges
_ARABIC_LETTER_RE = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]'
)

# Latin letter ranges
_LATIN_LETTER_RE = re.compile(
    r'[\u0041-\u007A\u00C0-\u024F]'
)


@dataclass
class LanguageSegment:
    """A contiguous segment of text in one language."""
    language: Literal["ar", "en", "mixed"]
    text: str
    start: int
    end: int


# ──────────────────────────────────────────────
# Diacritization detection
# ──────────────────────────────────────────────


def detect_diacritization_level(text: str) -> float:
    """
    Measure the diacritization level of Arabic text.

    Returns ratio of diacritical marks to Arabic letters (0.0 to ~1.0).
    A fully diacritized text typically scores 0.3–0.5+.

    Interpretation:
    - < 0.05  → undiacritized
    - 0.05–0.30 → partial
    - > 0.30 → diacritized
    """
    arabic_letters = sum(1 for c in text if _ARABIC_LETTER_RE.match(c) and c not in _ARABIC_DIACRITICS)
    diacritics = sum(1 for c in text if c in _ARABIC_DIACRITICS)

    if arabic_letters == 0:
        return 0.0

    return diacritics / arabic_letters


def classify_diacritization(text: str) -> Literal["undiacritized", "partial", "diacritized"]:
    """
    Classify text diacritization level.

    Returns one of: "undiacritized", "partial", "diacritized".
    """
    level = detect_diacritization_level(text)

    if level < DIACRITIZATION_UNDIACRITIZED:
        return "undiacritized"
    elif level < DIACRITIZATION_PARTIAL:
        return "partial"
    else:
        return "diacritized"


def auto_diacritize(text: str, engine: str = "mishkal") -> str:
    """
    Auto-diacritize Arabic text.

    Primary engine: Mishkal (lightweight, good for MSA).
    Fallback: returns original text with a warning.

    Requires: pip install mishkal (optional dependency).
    """
    if engine == "mishkal":
        try:
            import mishkal.tashkeel

            vocalizer = mishkal.tashkeel.TashkeelClass()
            result = vocalizer.tashkeel(text)
            return result
        except ImportError:
            # Mishkal not installed — return original
            return text
        except Exception:
            return text

    return text


def is_arabic(text: str) -> bool:
    """Check if text is predominantly Arabic."""
    if not text.strip():
        return False
    arabic_chars = sum(1 for c in text if _ARABIC_LETTER_RE.match(c))
    total_letters = sum(1 for c in text if unicodedata.category(c).startswith('L'))
    if total_letters == 0:
        return False
    return (arabic_chars / total_letters) > 0.5


def is_latin(text: str) -> bool:
    """Check if text is predominantly Latin script."""
    if not text.strip():
        return False
    latin_chars = sum(1 for c in text if _LATIN_LETTER_RE.match(c))
    total_letters = sum(1 for c in text if unicodedata.category(c).startswith('L'))
    if total_letters == 0:
        return False
    return (latin_chars / total_letters) > 0.5


# ──────────────────────────────────────────────
# Language segment detection
# ──────────────────────────────────────────────


def detect_language_segments(text: str) -> list[LanguageSegment]:
    """
    Split text into language-tagged segments (Arabic vs Latin).

    Each word is classified, then contiguous runs of the same
    language are merged into segments.
    """
    if not text.strip():
        return []

    words = text.split()
    if not words:
        return []

    segments: list[LanguageSegment] = []
    current_lang: Literal["ar", "en", "mixed"] = _classify_word(words[0])
    current_words: list[str] = [words[0]]
    current_start = 0

    for i, word in enumerate(words[1:], start=1):
        word_lang = _classify_word(word)

        # Punctuation-only or numbers inherit current language
        if word_lang == "mixed":
            current_words.append(word)
            continue

        if word_lang == current_lang:
            current_words.append(word)
        else:
            # Language switch — flush current segment
            seg_text = " ".join(current_words)
            seg_start = text.find(seg_text, current_start)
            segments.append(LanguageSegment(
                language=current_lang,
                text=seg_text,
                start=seg_start,
                end=seg_start + len(seg_text),
            ))
            current_start = seg_start + len(seg_text)
            current_lang = word_lang
            current_words = [word]

    # Flush final segment
    if current_words:
        seg_text = " ".join(current_words)
        seg_start = text.find(seg_text, current_start)
        if seg_start == -1:
            seg_start = current_start
        segments.append(LanguageSegment(
            language=current_lang,
            text=seg_text,
            start=seg_start,
            end=seg_start + len(seg_text),
        ))

    return segments


def _classify_word(word: str) -> Literal["ar", "en", "mixed"]:
    """Classify a single word as Arabic, English/Latin, or mixed/other."""
    arabic = sum(1 for c in word if _ARABIC_LETTER_RE.match(c))
    latin = sum(1 for c in word if _LATIN_LETTER_RE.match(c))

    if arabic > 0 and latin == 0:
        return "ar"
    elif latin > 0 and arabic == 0:
        return "en"
    else:
        return "mixed"


# ──────────────────────────────────────────────
# Dialect-voice matching
# ──────────────────────────────────────────────


def validate_dialect_voice_match(
    dialect: str | None,
    voice: str | None,
) -> str | None:
    """
    Check if dialect and voice are a reasonable match.

    Returns a warning string if mismatched, None if OK.
    Does NOT block — informational only.
    """
    if not dialect or not voice:
        return None

    expected_voices = DIALECT_VOICE_MAP.get(dialect, [])
    if not expected_voices:
        return None

    # Check if the voice's locale prefix matches the dialect's expected voices
    voice_prefix = voice.split("-")[0:2]  # e.g., ["ar", "SA"]
    voice_locale = "-".join(voice_prefix)  # e.g., "ar-SA"

    expected_locales = set()
    for ev in expected_voices:
        parts = ev.split("-")[0:2]
        expected_locales.add("-".join(parts))

    if voice_locale not in expected_locales:
        return (
            f"Dialect '{dialect}' typically uses voices from "
            f"{expected_locales}, but voice '{voice}' is from '{voice_locale}'. "
            f"This may produce unexpected prosody."
        )

    return None