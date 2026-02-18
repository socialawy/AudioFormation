# Arabic Text Processing in AudioFormation

Arabic is treated as a first-class language, not an afterthought.

## Diacritics (تشكيل)

Undiacritized Arabic is ambiguous. The same consonant skeleton can represent
multiple words. TTS quality depends on correct diacritization.

### Detection

```python
from audioformation.utils.arabic import detect_diacritization_level

level = detect_diacritization_level("مرحبا بالعالم")
# Returns: 0.0 (undiacritized)

level = detect_diacritization_level("مَرْحَبًا بِالْعَالَمِ")
# Returns: ~0.45 (diacritized)
```
### Thresholds:
- < 5% → undiacritized → auto-diacritize
- 5–30% → partial → warn, offer auto-diacritize
- > 30% → diacritized → pass through

### Auto-Diacritization (Mishkal)
```python
from audioformation.utils.arabic import auto_diacritize

result = auto_diacritize("مرحبا بالعالم")
# result["text"] = "مَرْحَبَا بِالْعَالَمِ"
# result["before_level"] = 0.0
# result["after_level"] = 0.42
```
#### Engine: Mishkal (pip install mishkal)

- Lightweight, fast, pure Python
- Good for MSA (Modern Standard Arabic)
- Sufficient for literary Arabic

#### Pipeline Integration
```bash
audioformation validate MY_NOVEL
# ⚠ Chapter 'ch01': Arabic text is undiacritized.
```
## Dialect-Voice Matching
- Characters can declare their dialect in project.json:
```json
{
  "narrator": {
    "dialect": "msa",
    "voice": "ar-SA-HamedNeural"
  }
}
```
- Validation warns on mismatches (e.g., Egyptian dialect with Saudi voice)
- but does not block — users may intentionally cross-match.
- Supported dialects: msa, eg, sa, ae, lb

## Mixed Arabic-English Text
Detection uses Unicode block analysis:

Arabic: U+0600–U+06FF, U+0750–U+077F, U+FB50–U+FDFF
Latin: U+0041–U+007A, U+00C0–U+024F
### Chunking rules:

- Short inline English (1–3 words) stays in Arabic chunk
- Longer English passages (>10 words) get separate chunks
- XTTS: always split at language boundary (mid-sentence switching unreliable)
- Edge-tts: Arabic voice handles short English acceptably

### Language Segment Detection
```python
from audioformation.utils.arabic import detect_language_segments

segments = detect_language_segments("مرحبا Hello World مرحبا")
# [Segment(lang="ar", text="مرحبا"), Segment(lang="en", text="Hello World"), ...]
```
