# AudioFormation TTS Engine Guide

## Available Engines

| Engine | Type | Voice Cloning | SSML | GPU Required | Status |
|---|---|---|---|---|---|
| `edge` | Cloud (free) | No | Yes | No | ✅ Primary |
| `gtts` | Cloud (free) | No | No | No | ✅ Fallback |
| `xtts` | Local | Yes | No | Recommended | ✅ Built |
| `elevenlabs` | Cloud (paid/free tier) | Yes | No | No | ✅ Built |

## edge-tts (Primary)

Microsoft's free neural voices via unofficial wrapper.

```bash
audioformation engines test edge
audioformation engines voices edge --lang ar
```
### Arabic voices:
ar-SA-HamedNeural — MSA (recommended default)
ar-EG-SalmaNeural / ar-EG-ShakirNeural — Egyptian
ar-AE-FatimaNeural / ar-AE-HamdanNeural — Emirati

### SSML support:
Pace, energy, emotion mapped via direction field.

### Known issues:

v7+ required (v6 has 403 DRM errors)
No SLA — Microsoft can change/block without notice
Rate limiting at high concurrency

## gTTS (Emergency Fallback)
Google Translate TTS. Lower quality but zero-auth, always available.

Activated automatically when edge-tts returns 403/500.
```bash
audioformation quick "test" --engine gtts -o test.mp3
```

## XTTS v2 (Voice Cloning)
Local inference via Coqui TTS (Idiap community fork).

### Requirements:

- pip install coqui-tts (pinned 0.27.x)
- transformers<5 (v5 breaks Coqui)
- 4GB+ VRAM recommended (CPU fallback available)
- 6–10 second reference audio per voice
```bash
audioformation cast clone MY_NOVEL --name "Hero" --reference ./hero.wav --engine xtts
audioformation generate MY_NOVEL --engine xtts --device gpu
```
### VRAM strategies:

- empty_cache_per_chapter — default, clears cache between chapters
- conservative — unloads model after each chapter
- reload_periodic — unloads every N chapters

### Performance (GTX 1650 Ti, 4GB):

- Model load: ~15s (cached), ~775s (first download)
- Per chunk: ~3.8s (200 chars, Arabic)
- VRAM usage: ~2.0 GB (1.5 GB headroom)

## ElevenLabs (Cloud Premium)
High-quality cloud TTS with voice cloning. Requires API key.

Configure in 00_CONFIG/engines.json or set ELEVENLABS_API_KEY env var.

## Engine Fallback Chain
```text
Primary engine (per character) → fallback_chain engines

Scope: "chapter" — retry primary each chapter (default)
Scope: "project" — switch permanently after first failure
```
- Configure in generation.fallback_scope and generation.fallback_chain.
