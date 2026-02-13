"""
Arabic text processing — diacritization, language detection, segmentation.

Handles the harder case first: Arabic diacritics, mixed Arabic-English text,
and dialect-voice matching.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Arabic Unicode ranges
_ARABIC_BLOCK = range(0x0600, 0x0700)
_ARABIC_SUPPLEMENT = range(0x0750, 0x0780)
_ARABIC_PRESENTATION_A = range(0xFB50, 0xFE00)
_ARABIC_PRESENTATION_B = range(0xFE70, 0xFF00)

# Diacritical marks (tashkeel)
_DIACRITICS = set(
    "\u064B\u064C\u064D\u064E\u064F\u0650"  # tanween + fatha/damma/kasra
    "\u0651\u0652\u0653\u0654\u0655"          # shadda, sukun, etc.
    "\u0656\u0657\u0658\u065A\u065B"          # additional marks
    "\u0670"                                    # superscript alef
)

# Latin Unicode ranges
_LATIN_BASIC = range(0x0041, 0x007B)      # A-Z, a-z
_LATIN_EXTENDED = range(0x00C0, 0x0250)   # accented characters

# Dialect to voice mapping (edge-tts)
DIALECT_VOICE_MAP = {
    "msa": ["ar-SA-HamedNeural", "ar-SA-ZariyahNeural"],
    "sa": ["ar-SA-HamedNeural", "ar-SA-ZariyahNeural"],
    "eg": ["ar-EG-SalmaNeural", "ar-EG-ShakirNeural"],
    "ae": ["ar-AE-FatimaNeural", "ar-AE-HamdanNeural"],
    "lb": ["ar-LB-LaylaNeural", "ar-LB-RamiNeural"],
    "sy": ["ar-SY-AmanyNeural", "ar-SY-LaithNeural"],
    "iq": ["ar-IQ-BasselNeural", "ar-IQ-RanaNeural"],
    "ma": ["ar-MA-JamalNeural", "ar-MA-MounaNeural"],
    "tn": ["ar-TN-HediNeural", "ar-TN-ReemNeural"],
    "jo": ["ar-JO-SanaNeural", "ar-JO-TaimNeural"],
    "kw": ["ar-KW-FahedNeural", "ar-KW-NouraNeural"],
    "qa": ["ar-QA-AmalNeural", "ar-QA-MoazNeural"],
    "bh": ["ar-BH-AliNeural", "ar-BH-LailaNeural"],
}


@dataclass
class LanguageSegment:
    """A contiguous text segment with detected language."""
    text: str
    language: str  # "ar" or "en"
    start: int = 0
    end: int = 0


@dataclass
class DiacritizationResult:
    """Result of diacritization analysis/processing."""
    original: str
    diacritized: str
    level_before: float
    level_after: float
    engine: str = "mishkal"
    warnings: list[str] = field(default_factory=list)


def is_arabic_char(char: str) -> bool:
    """Check if a character is in any Arabic Unicode block."""
    cp = ord(char)
    return (
        cp in _ARABIC_BLOCK
        or cp in _ARABIC_SUPPLEMENT
        or cp in _ARABIC_PRESENTATION_A
        or cp in _ARABIC_PRESENTATION_B
    )


def is_latin_char(char: str) -> bool:
    """Check if a character is Latin."""
    cp = ord(char)
    return cp in _LATIN_BASIC or cp in _LATIN_EXTENDED


def is_diacritic(char: str) -> bool:
    """Check if a character is an Arabic diacritical mark."""
    return char in _DIACRITICS


def detect_diacritization_level(text: str) -> float:
    """
    Measure the diacritization level of Arabic text.

    Returns a float 0.0-1.0:
        < 0.05  → undiacritized
        0.05-0.30 → partially diacritized
        > 0.30  → diacritized

    Only counts Arabic letter characters (not spaces, punctuation, digits).
    """
    arabic_letters = 0
    diacritic_count = 0

    for char in text:
        if is_diacritic(char):
            diacritic_count += 1
        elif is_arabic_char(char) and not char.isspace():
            # Count base letters only (exclude diacritics, spaces)
            cat = unicodedata.category(char)
            if cat.startswith("L"):  # Letter category
                arabic_letters += 1

    if arabic_letters == 0:
        return 0.0

    return diacritic_count / arabic_letters


def classify_diacritization(text: str) -> str:
    """
    Classify text diacritization level.

    Returns: "undiacritized", "partial", or "diacritized"
    """
    level = detect_diacritization_level(text)
    if level < 0.05:
        return "undiacritized"
    elif level < 0.30:
        return "partial"
    else:
        return "diacritized"


def detect_language(text: str) -> str:
    """
    Detect primary language of text based on Unicode character analysis.

    Returns "ar" or "en". Defaults to "ar" for mixed/ambiguous text.
    """
    arabic_count = 0
    latin_count = 0

    for char in text:
        if is_arabic_char(char):
            arabic_count += 1
        elif is_latin_char(char):
            latin_count += 1

    if arabic_count == 0 and latin_count == 0:
        return "ar"  # Default

    total = arabic_count + latin_count
    if arabic_count / total > 0.3:
        return "ar"
    return "en"


def detect_language_segments(text: str) -> list[LanguageSegment]:
    """
    Split text into contiguous language segments.

    Identifies runs of Arabic vs Latin characters, treating short
    inline segments (1-3 words) as part of the surrounding language.
    """
    if not text.strip():
        return []

    # First pass: tag each word
    words = text.split()
    tagged: list[tuple[str, str]] = []

    for word in words:
        ar_chars = sum(1 for c in word if is_arabic_char(c))
        lat_chars = sum(1 for c in word if is_latin_char(c))

        if ar_chars >= lat_chars:
            tagged.append((word, "ar"))
        else:
            tagged.append((word, "en"))

    if not tagged:
        return []

    # Second pass: merge runs, absorb short inline switches
    segments: list[LanguageSegment] = []
    current_lang = tagged[0][1]
    current_words: list[str] = [tagged[0][0]]

    for word, lang in tagged[1:]:
        if lang == current_lang:
            current_words.append(word)
        else:
            # Check if this is a short inline switch (1-3 words)
            lookahead_same = 0
            for fw, fl in tagged[tagged.index((word, lang)):]:
                if fl == lang:
                    lookahead_same += 1
                else:
                    break

            if lookahead_same <= 3:
                # Absorb into current segment
                current_words.append(word)
            else:
                # Genuine language switch
                segments.append(LanguageSegment(
                    text=" ".join(current_words),
                    language=current_lang,
                ))
                current_lang = lang
                current_words = [word]

    # Flush last segment
    if current_words:
        segments.append(LanguageSegment(
            text=" ".join(current_words),
            language=current_lang,
        ))

    return segments


def split_at_language_boundaries(
    text: str, max_chars: int = 200
) -> list[LanguageSegment]:
    """
    Split text respecting language boundaries and max chunk size.

    Never splits mid-word. Prefers splitting at language transitions.
    """
    segments = detect_language_segments(text)
    result: list[LanguageSegment] = []

    for segment in segments:
        if len(segment.text) <= max_chars:
            result.append(segment)
        else:
            # Split long segments at sentence boundaries
            sentences = re.split(r'(?<=[.!?؟،])\s+', segment.text)
            
            # If no sentence boundaries found, split by spaces to respect max_chars
            if len(sentences) == 1:
                words = segment.text.split()
                sentences = []
                current_sentence = ""
                for word in words:
                    test_sentence = f"{current_sentence} {word}".strip() if current_sentence else word
                    if len(test_sentence) > max_chars:
                        if current_sentence:
                            sentences.append(current_sentence)
                        current_sentence = word
                    else:
                        current_sentence = test_sentence
                if current_sentence:
                    sentences.append(current_sentence)
            
            current_chunk = ""

            for sentence in sentences:
                if (
                    current_chunk
                    and len(current_chunk) + len(sentence) + 1 > max_chars
                ):
                    result.append(LanguageSegment(
                        text=current_chunk.strip(),
                        language=segment.language,
                    ))
                    current_chunk = sentence
                else:
                    current_chunk = (
                        f"{current_chunk} {sentence}" if current_chunk
                        else sentence
                    )

            if current_chunk.strip():
                result.append(LanguageSegment(
                    text=current_chunk.strip(),
                    language=segment.language,
                ))

    return result


def auto_diacritize(text: str, engine: str = "mishkal") -> DiacritizationResult:
    """
    Auto-diacritize Arabic text.

    Args:
        text: Arabic text to diacritize.
        engine: Diacritization engine ("mishkal" or "camel").

    Returns DiacritizationResult with before/after levels.
    """
    level_before = detect_diacritization_level(text)
    warnings: list[str] = []

    if engine == "mishkal":
        diacritized = _diacritize_mishkal(text)
    else:
        warnings.append(f"Unknown diacritization engine: {engine}, using mishkal")
        diacritized = _diacritize_mishkal(text)

    level_after = detect_diacritization_level(diacritized)

    if level_after < 0.30:
        warnings.append(
            f"Diacritization level still low after processing: "
            f"{level_after:.1%}. Manual review recommended."
        )

    return DiacritizationResult(
        original=text,
        diacritized=diacritized,
        level_before=level_before,
        level_after=level_after,
        engine=engine,
        warnings=warnings,
    )


def _diacritize_mishkal(text: str) -> str:
    """Diacritize using Mishkal library."""
    try:
        from mishkal.tashkeel import TashkeelClass
        tashkeel = TashkeelClass()
        result = tashkeel.tashkeel(text)
        return result.strip() if result else text
    except ImportError:
        return text
    except Exception as e:
        return text


def diacritize_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    engine: str = "mishkal",
) -> DiacritizationResult:
    """
    Diacritize an Arabic text file.

    If output_path is None, writes to input_path with .diacritized.txt suffix.
    """
    text = input_path.read_text(encoding="utf-8")

    if output_path is None:
        output_path = input_path.with_suffix(".diacritized.txt")

    result = auto_diacritize(text, engine=engine)
    output_path.write_text(result.diacritized, encoding="utf-8")

    return result


def validate_dialect_voice_match(
    dialect: Optional[str], voice: Optional[str]
) -> Optional[str]:
    """
    Check if dialect and voice are compatible.

    Returns a warning string if mismatched, None if OK or not applicable.
    """
    if not dialect or not voice:
        return None

    dialect = dialect.lower()
    if dialect not in DIALECT_VOICE_MAP:
        return f"Unknown dialect '{dialect}'. Known: {list(DIALECT_VOICE_MAP.keys())}"

    expected_voices = DIALECT_VOICE_MAP[dialect]

    # Extract region code from voice name (e.g., "ar-SA" from "ar-SA-HamedNeural")
    voice_parts = voice.split("-")
    if len(voice_parts) >= 2:
        voice_region = f"{voice_parts[0]}-{voice_parts[1]}"

        # Check if any expected voice matches the region
        expected_regions = set()
        for ev in expected_voices:
            ep = ev.split("-")
            if len(ep) >= 2:
                expected_regions.add(f"{ep[0]}-{ep[1]}")

        if voice_region not in expected_regions:
            return (
                f"Dialect '{dialect}' typically uses voices from "
                f"{expected_regions}, but voice '{voice}' is from "
                f"'{voice_region}'. This may affect pronunciation accuracy."
            )

    return None