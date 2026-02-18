
# 🏭 AudioFormation — Planning/ARCHITECTURE Document


## Production audio pipeline: Voice, SFX, Music, Mix, Export.

Companion to VideoFormation (same architecture, different domain). 

### Philosophy (Mirrors VideoFormation)

Principle	| Implementation
-----------|---------------
Single Source of Truth	| project.json governs everything
Validation Gates	| Hard gates before generation, mixing, export
Automation First	| CLI drives pipeline; dashboard is a bonus
Engine Agnostic	| Swap TTS/music engines without touching project files
Hardware Aware	| Auto-detects GPU, suggests optimal engine
Bilingual First	| Arabic + English as primary languages

### Architecture
```text
┌─────────────────────────────────────────────────────┐
│                 audioformation CLI                  │
│         python -m audioformation <command>          │
├─────────────────────────────────────────────────────┤
│                   FastAPI Server                    │
│               localhost:4001/api/*                  │
├──────┬──────┬──────┬──────┬─────────────────────────┤
│ Vox  │ FX   │Comp  │ Mix  │ Ship                    │
│Engine│Forge │Engine│ Bus  │ (Export)                │
├──────┴──────┴──────┴──────┴─────────────────────────┤
│              Project Manager                        │
│        (JSON-driven, file-system backed)            │
├─────────────────────────────────────────────────────┤
│            Web Dashboard (localhost:4001)           │
│     Projects │ Editor │ Timeline │ Mix │ Export     │
└─────────────────────────────────────────────────────┘
```
### Five Engines
1. VoxEngine (Voice/Narration)
```text
Providers (priority order):
├── edge-tts # ✅ BUILT: Free, fast, excellent Arabic
│ ├── Voices: ar-SA-HamedNeural, ar-EG, ar-AE-FatimaNeural, etc.
│ ├── Full list: edge-tts --list-voices | grep ar-
│ ├── ✅ BUILT: Tested with Arabic content
│ ├── ⚠️ PATCHED: Upgraded to v7 to resolve 403 DRM token errors
│ └── Risk: unofficial MS wrapper, no SLA, IP throttle at heavy scale
│
├── gtts # ✅ BUILT: Emergency fallback engine
│ ├── Google Translate TTS, free tier
│ ├── Activated on edge-tts 403/500 errors
│ ├── Quality: Acceptable for emergencies, not primary
│ └── No API key required, rate-limited
│
├── coqui-tts (XTTS-v2) # ✅ BUILT: Local voice cloning
│ ├── Install: pip install coqui-tts (Idiap community fork)
│ ├── 17 languages including Arabic
│ ├── 6-second voice clone from reference audio
│ ├── ✅ GPU validated: 1.5GB headroom on 4GB GTX 1650 Ti
│ ├── ✅ Performance: 3.8s per 200-char chunk
│ ├── ⚠️ CRITICAL: Long-form narration requires aggressive chunking
│ │ ├── Split text into breath-groups (2-3 sentences, max ~200 chars)
│ │ ├── Generate each chunk with SAME reference audio
│ │ ├── Crossfade chunks (50ms overlap)
│ │ ├── Fixed generation params across all chunks for consistency
│ │ └── Auto-retry failed chunks (max 3 attempts)
│ └── Pin version in pyproject.toml — community-maintained
│
├── elevenlabs # ✅ BUILT: Premium cloud fallback
│ └── Best overall quality, strong Arabic, free tier, pay-per-use, voice cloning support
│
├── openai-tts # Priority 4: If Arabic quality improves (Phase 5)
│
└── gemini-tts # Priority 5: If rate limits ease (Phase 5)

#### Built Engines Summary (Phase 1–2)

| Engine | Type | Status | Notes |
|:---|:---|:---|:---|
| **Edge-TTS** | Cloud | ✅ Phase 1 | Streaming synthesis, ~100ms latency, free tier |
| **gTTS** | Cloud | ✅ Phase 1 | Fallback engine, slow but reliable, no API key |
| **XTTS v2.0** | Local | ✅ Phase 2 | Speaker cloning, async generation, 30–60s per 10min |
| **ElevenLabs** | Cloud | ✅ Phase 2 | Voice ID mapping, pooled HTTP client, awaits API key |

Features:
├── Character profiles (voice + persona + direction per character)
├── Voice cloning workflow (reference audio → XTTS)
├── Chapter-aware chunking (auto-split long text at sentence boundaries)
├── Arabic diacritics preprocessing
├── Sentence-level retry on generation failure
├── ✅ BUILT: Engine fallback chain: edge-tts → gTTS → cloud engines
├── ✅ BUILT: Automatic retry with fallback on 403/500 errors
├── ✅ BUILT: Per-chunk QC scan (SNR, pitch continuity, duration sanity)
└── ✅ BUILT: Engine availability detection and graceful degradation

#### Engine Fallback Chain (✅ BUILT)

AudioFormation implements automatic engine fallback to ensure robust generation:

```text
Primary: edge-tts (v7+)
│ ├── Fast, high-quality Arabic voices
│ ├── Free, no API key required
│ └── ⚠️ PATCHED: v7 resolves 403 DRM token errors
│
Fallback 1: gTTS (✅ BUILT)
│ ├── Activated on edge-tts failures (403, 500, timeout)
│ ├── Google Translate TTS, free tier
│ ├── Quality: Acceptable for emergencies
│ └── Automatic retry with gTTS on edge-tts errors
│
Fallback 2: Cloud engines (✅ BUILT)
│ ├── ElevenLabs (Adapter ready), OpenAI TTS, Gemini TTS (Phase 3)
│ ├── Pay-per-use, premium quality
│ └── Configurable API keys in 00_CONFIG/engines.json
```

Implementation:
- src/audioformation/engines/registry.py: Engine priority and fallback logic
- src/audioformation/engines/gtts_engine.py: gTTS implementation
- src/audioformation/engines/elevenlabs.py: ElevenLabs cloud adapter (ready for API key)
- Automatic retry with next engine on generation failure
- User-configurable engine preferences per character

#### Test Infrastructure & Coverage

**371 tests (100% passing), all isolated and mocked:**

| Characteristic | Status | Notes |
|:---|:---|:---|
| Real API calls (edge-tts, gTTS, ElevenLabs) | ❌ None | All tests use MagicMock/AsyncMock |
| Network dependency | ❌ None | CI/CD fully deterministic |
| Test runtime | ✅ 10.7s | Fast, parallelizable suite |
| Isolation strategy | ✅ Complete | `conftest.py` monkeypatches PROJECTS_ROOT to tmp_path |
| Coverage by area | ✅ Comprehensive | Text handling, chunking, engines (abstract), multi-speaker, export, validation, QC |
| Real-world API validation | ⚠️ Manual only | Tested outside automated suite (documented in BUILD_LOG) |

**Test mocking approach:**
- Engine tests: Use `MagicMock` for TTS library (torch, coqui-tts) and `AsyncMock` for async generation
- Project tests: Redirect `PROJECTS_ROOT` to isolated `tmp_path`  
- External services: Mock httpx for ElevenLabs, mock edge-tts responses
- No environment variables required (API keys auto-mocked)

- SSML Direction Mapping (edge-tts)

The `direction` field in chapter schema maps to SSML parameters,
giving edge-tts actual voice control beyond plain text.
```text
Direction Field → SSML Mapping:

pace:
├── "very slow" → <prosody rate="slowest">
├── "slow" → <prosody rate="slow">
├── "moderate" → (no tag)
├── "fast" → <prosody rate="fast">
└── "very fast" → <prosody rate="fastest">

energy:
├── "whisper" → <prosody volume="x-soft">
├── "quiet" → <prosody volume="soft">
├── "normal" → (no tag)
├── "loud" → <prosody volume="loud">
└── "intense" → <prosody volume="x-loud">

emotion:
├── Mapped to emphasis + pitch combinations
├── "wonder" → <emphasis level="moderate"><prosody pitch="+10%">
├── "sadness" → <emphasis level="reduced"><prosody pitch="-5%">
├── "tension" → <emphasis level="strong"><prosody pitch="+15%">
└── Custom values → logged as unsupported, no SSML applied

Inline markers in text:
├── ... (ellipsis) → <break time="500ms"/>
├── — (em dash) → <break time="300ms"/>
└── Paragraph break → <break time="1000ms"/>

```python
# src/audioformation/engines/edge_tts.py
def direction_to_ssml(text: str, direction: dict) -> str:
    """Wrap text in SSML tags based on direction config."""
```
- For XTTS: Direction field affects reference audio selection
and generation parameters, not SSML (XTTS doesn't support SSML).
Direction is engine-adaptive.

2. FXForge (Sound Effects)
```text
Modes:
├── Procedural       # Oscillator-based synthesis
│   ├── Ambient pads (drone, atmosphere)
│   ├── UI sounds (click, hover, confirm)
│   ├── Narrative SFX (whoosh, impact, transition)
│   └── Custom (frequency, filter, envelope params in JSON)
│
├── Sample-based     # Import WAV/MP3 files
│   └── Trim, normalize, tag, catalog
│
└── Hybrid           # Layer procedural + samples
```
3. ComposeEngine (Music/Composition)
```text
Tier 1: Ambient Pad Generator ← PHASE 2 (this is what audiobooks need)
├── Drone + filtered noise + LFO modulation
├── Mood presets: contemplative, tense, wonder, melancholy, triumph
├── Loopable, non-fatiguing, configurable duration
├── Pure numpy synthesis → WAV output
└── Good enough for 90% of audiobook background needs

Tier 2: Import + Process ← PHASE 3
├── Import royalty-free music files (WAV/MP3)
├── Auto-trim, fade, normalize
├── Loop-point detection
├── Catalog in 05_MUSIC/catalog.json
└── Tag with mood/tempo/key metadata

Tier 3: Algorithmic Composition ← PHASE 4 (only if Tier 1+2 insufficient)
├── Constrained grammar + heavy preset library
├── Scale/key-aware generation
├── MIDI export for external refinement
├── Consider FishAudio-S1 or IndexTTS integration if mature by then
└── NOT in v1.0 scope — code exists from prototypes, park it

NOTE: Pure algorithmic music without heavy presets & rules sounds
immediately recognizable as "AI slop." Ambient pads are the honest
path for audiobook production. Saving composition ambitions for v2.0.
```
4. MixBus (Mixing/Layering)
```text
Features:
├── Multi-track timeline (voice + SFX + music)
├── Per-track volume, pan, fade in/out
├── Chapter assembly (stitch segments in order)
├── Normalization (LUFS targeting for broadcast)
│ ├── Measure: pyloudnorm (in-process, per-file)
│ ├── Normalize: ffmpeg loudnorm filter (batch, fast)
│ └── Target: -16 LUFS integrated (audiobook standard)
├── Auto-ducking (voice-triggered music attenuation)
│ ├── Trigger: silero-vad v6.2 (voice activity detection)
│ ├── NOT energy-based (Arabic speech has dynamic energy — VAD is more robust)
│ ├── Look-ahead buffer: 200ms before voiced region
│ ├── Gain ramp: 100ms attack, 500ms release
│ ├── Attenuation: -12 dB default (configurable)
│ └── Output: gain-envelope applied to music track before mix
└── Preview before export
```
5. ShipIt (Export)
```text
Formats:
├── WAV (lossless, production master)
├── MP3 (distribution, configurable bitrate via ffmpeg)
├── FLAC (lossless compressed, archival)
├── M4B (audiobook with chapter markers) ← PRIMARY FORMAT
└── MIDI (from ComposeEngine, if used)

M4B Audiobook Pipeline (ffmpeg + mutagen):
├── 1. Validate cover art
│ Required: JPEG or PNG
│ Dimensions: 1400×1400 minimum, 3000×3000 maximum
│ Aspect ratio: must be square (1:1)
│ Fail export with clear message if invalid
│ (iTunes/Audible reject non-compliant covers)
│
├── 2. Apply chapter transitions
│ Default: silence (gap_between_chapters_sec)
│ Optional: transition sound file
│ Config: "chapter_transition": "silence" | "path/to/chime.wav"
│
├── 3. Concatenate chapter WAVs → single file
│ ffmpeg -f concat -i chapters.txt -c copy concat.wav
│
├── 4. Encode to AAC
│ ffmpeg -i concat.wav -c:a aac -b:a 128k -movflags +faststart body.m4a
│
├── 5. Write chapter metadata file (ffmetadata format)
│ [CHAPTER] TIMEBASE=1/1000 START=0 END=180000 title=Chapter 1
│
├── 6. Merge metadata
│ ffmpeg -i body.m4a -i metadata.txt -map_metadata 1 -c copy output.m4b
│
├── 7. Embed cover art + ID3 tags via mutagen
│
└── 8. Generate manifest.json with SHA256 checksums per file
```

## Project Structure
```text
PROJECTS/
└── MY_NOVEL_2026/
    ├── project.json          # Single source of truth
    ├── pipeline-status.json  # Node execution state
    │
    ├── 00_CONFIG/
    │   ├── characters.json   # Voice profiles + personas
    │   ├── engines.json      # Engine preferences + API keys
    │   └── hardware.json     # Auto-detected capabilities
    │
    ├── 01_TEXT/
    │   ├── chapters/
    │   │   ├── ch01.txt
    │   │   ├── ch02.txt
    │   │   └── ...
    │   └── metadata.json     # Chapter order, language tags
    │
    ├── 02_VOICES/
    │   ├── references/       # Voice cloning samples
    │   │   ├── narrator.wav
    │   │   └── hero.wav
    │   └── profiles.json     # Voice-to-character mapping
    │
    ├── 03_GENERATED/
    │   ├── raw/              # Direct TTS output
    │   └── processed/        # Post-processed (normalized)
    │
    ├── 04_SFX/
    │   ├── procedural/       # Generated SFX
    │   ├── samples/          # Imported samples
    │   └── catalog.json      # SFX registry
    │
    ├── 05_MUSIC/
    │   ├── generated/        # Algorithmic compositions
    │   ├── imported/         # Brought-in tracks
    │   └── midi/             # MIDI exports
    │
    ├── 06_MIX/
    │   ├── sessions/         # Mix configurations
    │   └── renders/          # Mixed output (pre-export)
    │
    └── 07_EXPORT/
        ├── audiobook/        # Final M4B/MP3
        ├── chapters/         # Individual chapter exports
        └── manifest.json     # Export log + checksums
```
## Security & Project Hygiene

### Threat Model (Scoped)
Threats addressed:
├── Path traversal from user input (project IDs, file paths)
├── Injection in filenames (chapter names → file system)
├── API key exposure in version control
└── Malformed project.json causing crashes

NOT in scope (v1.0):
├── Multi-user authentication
├── Network-facing deployment security
└── DRM / content protection

### Implementation
src/audioformation/utils/security.py:
├── sanitize_project_id(id) → str # alphanumeric + underscore + hyphen only
├── sanitize_filename(name) → str # strip path separators, null bytes
├── validate_path_within(path, root) → bool # prevent traversal
└── redact_api_keys(config) → dict # for logging

### Auto-Generated .gitignore

Bootstrap creates `.gitignore` in every project:

```gitignore
# API keys — NEVER commit
00_CONFIG/engines.json

# Generated audio (large files)
03_GENERATED/**/*.wav
03_GENERATED/**/*.mp3
04_SFX/procedural/**/*.wav
05_MUSIC/generated/**/*.wav
06_MIX/renders/**/*.wav

# Exports
07_EXPORT/**/*.mp3
07_EXPORT/**/*.m4b
07_EXPORT/**/*.wav

# Keep directory structure
!**/.gitkeep
```

Port Assignments
```text
AudioFormation Dashboard:  localhost:4001
AudioFormation API:        localhost:4001
VideoFormation Dashboard:  localhost:3000
VideoFormation API:        localhost:3001
```
- No collisions. Both can run simultaneously.


## Pipeline Nodes
```text
┌───────────────────────────────────────────────────────────────┐
│                   PIPELINE STATE MACHINE                      │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│ [NEW PROJECT]                                                 │
│                                                               │
│       ▼                                                       │
│ ┌───────────┐                                                 │
│ │0:Bootstrap│  Create folders, detect hardware                │
│ └─────┬─────┘                                                 │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │1:Ingest  │  Import text, assign languages                   │
│ └─────┬────┘                                                  │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │2:Validate│ ◄── HARD GATE                                    │
│ └─────┬────┘                                                  │
│       │                                                       │
│       │ Checks:                                               │
│       │ • Text files exist + non-empty                        │
│       │ • Characters defined + voices assigned                │
│       │ • Engine available (GPU/network test)                 │
│       │ • Arabic diacritics preprocessed                      │
│       │ • LUFS target defined                                 │
│       │                                                       │
│ ┌─────┴────────┐                                              │
│ │ [PASS] FAIL] │ ──► fix & retry                              │
│ └─────┬────────┘                                              │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │3:Generate│  Run TTS per chapter/character                   │
│ └─────┬────┘                                                  │
│       │   • Chunk text into breath-groups                     │
│       │   • Generate per-chunk with engine                    │
│       │   • Crossfade chunks                                  │
│       │   • Measure LUFS + true-peak per file                 │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │3.5:QC    │ ◄── AUTO GATE (per chunk)                        │
│ └─────┬────┘  Checks per chunk:                               │
│       │   • SNR > threshold                                   │
│       │   • Short-time energy variance                        │
│       │   • Pitch continuity (catch glitches)                 │
│       │   • Duration sanity (expected ±30%)                   │
│       │   • Clipping detection (> -0.5 dBFS)                  │
│       │   • LUFS within ±3 of target                          │
│       │                                                       │
│       │ Results: PASS / WARN / FAIL                           │
│       │ FAIL → auto-retry (max 3)                             │
│       │ >5% FAIL rate → halt pipeline                         │
│       │ Output: qc_report.json                                │
│       │                                                       │
│ ┌─────┴─────┐                                                 │
│ │ [PASS]    │ [>5% FAIL]──► review qc_report, fix & retry     │
│ └─────┬─────┘                                                 │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │4:Process │  Normalize (ffmpeg loudnorm to target)           │
│ └─────┬────┘  Trim silence, consistent gaps                   │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │5:Compose │  (Optional) Ambient pads / import music          │
│ └─────┬────┘                                                  │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │6:Mix     │  Layer voice + SFX + music                       │
│ └─────┬────┘  VAD-based ducking (silero-vad)                  │
│       │      Chapter assembly                                 │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │7:QC Final│ ◄── HARD GATE                                    │
│ └─────┬────┘  Checks on mixed output:                         │
│       │   • Integrated LUFS within ±1 of target               │
│       │   • True-peak < -1.0 dBTP                             │
│       │   • No silence gaps > configured max                  │
│       │   • No clipping in final mix                          │
│       │   • Chapter boundaries aligned                        │
│       │                                                       │
│ ┌─────┴─────┐                                                 │
│ │ [PASS]    │ [FAIL]──► remix & retry                         │
│ └─────┬─────┘                                                 │
│       ▼                                                       │
│ ┌──────────┐                                                  │
│ │8:Export  │  Render final formats                            │
│ └──────────┘  MP3 + M4B + metadata + checksums                │
│              manifest.json with SHA256                        │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Node Summary Table

| Node | Name | Status | Description |
|---|---|---|---|
| 0–8 | All nodes | ✅ BUILT + E2E VERIFIED | Full pipeline tested end-to-end Feb 17, 2026 |

## Tech Stack
```text
## Tech Stack

| Layer | Technology | Why | Verified Status (Feb 2026) |
|---|---|---|---|
| Runtime | Python 3.11+ | All TTS libs are Python | ✅ Stable |
| API Server | FastAPI + Uvicorn | Async, fast, auto-docs | ✅ Stable |
| CLI | Click | Clean, composable | ✅ Stable |
| Audio I/O | pydub + ffmpeg | Universal format support | ✅ Industry standard |
| TTS: Free | edge-tts (rany2/edge-tts) | ✅ BUILT v7 - Fixed 403 DRM errors |
| TTS: Fallback | gTTS (Google TTS) | ✅ BUILT - Emergency fallback engine |
| TTS: Local | coqui-tts (idiap fork) | Voice cloning, offline, XTTS-v2 | ⚠️ Coqui AI shutdown late 2024. Community fork by Idiap (pip install coqui-tts ~0.27.x). Pin version. Still best local cloning option. **transformers<5 (coqui-tts breaks with v5)** |
| TTS: Cloud | httpx | Generic API client | ✅ Stable |
| Synthesis | numpy + soundfile | Procedural audio generation | ✅ Stable |
| LUFS Metering | pyloudnorm + ffmpeg loudnorm | Dual approach: in-process analysis (pyloudnorm) + batch normalization (ffmpeg loudnorm filter) | ✅ pyloudnorm v0.2.0 Jan 2026. For batch: ffmpeg loudnorm faster |
| VAD (Ducking) | silero-vad v6.2 | Voice activity detection for ducking trigger | ✅ Excellent. CPU-efficient, low false positives. `pip install silero-vad` |
| Music | numpy + midiutil | Ambient pad generation + MIDI export | ✅ Stable |
| Audiobook Export | ffmpeg + mutagen | M4B with chapters, cover art, metadata | ✅ ffmpeg = canonical M4B tool. mutagen for ID3/cover. mp4v2 is legacy — skip it |
| Dashboard | Vanilla HTML/JS | Zero build step, portable | ✅ No dependencies |
| Packaging | PyInstaller (primary), Nuitka (benchmark later) | .exe distribution | ✅ PyInstaller safest for ML+audio stack. Nuitka faster startup if needed |
| Testing | pytest | Standard Python testing | ✅ Stable |
```

## Dependency Install (Reference)

```bash
pip install click fastapi uvicorn pydub edge-tts coqui-tts httpx mishkal
pip install numpy soundfile pyloudnorm silero-vad mutagen midiutil
pip install pytest httpx[test]
# System: ffmpeg must be on PATH
```

## Version Pinning Strategy
Pin coqui-tts and silero-vad explicitly in pyproject.toml.
These are community-maintained — treat as "stable but not guaranteed long-term."
All other dependencies are mature ecosystem packages with standard semver.

## CLI Design

```bash
# Project Management
audioformation new "MY_NOVEL"
audioformation list
audioformation status MY_NOVEL
audioformation hardware

# Pipeline Execution
audioformation ingest MY_NOVEL --source ./chapters/
audioformation validate MY_NOVEL
audioformation generate MY_NOVEL --engine edge
audioformation generate MY_NOVEL --engine xtts --device gpu
audioformation generate MY_NOVEL --engine xtts --device cpu
audioformation qc MY_NOVEL
audioformation qc MY_NOVEL --report
audioformation process MY_NOVEL
audioformation compose MY_NOVEL --preset contemplative
audioformation mix MY_NOVEL
audioformation qc-final MY_NOVEL
audioformation export MY_NOVEL --format mp3 --bitrate 192
audioformation export MY_NOVEL --format m4b

# Engine Management
audioformation engines list
audioformation engines test edge
audioformation engines test xtts --device gpu
audioformation engines voices edge --lang ar

# Character Management
audioformation cast list MY_NOVEL
audioformation cast add MY_NOVEL --name "Narrator" --voice ar-SA-HamedNeural --engine edge
audioformation cast clone MY_NOVEL --name "Hero" --reference ./hero.wav --engine xtts

# Quick Generation (no project needed)
audioformation quick "Hello world" --engine edge --voice en-US-GuyNeural -o hello.mp3
audioformation quick "مرحبا بالعالم" --engine edge --voice ar-SA-HamedNeural -o hello_ar.mp3
echo "مرحبا" | audioformation quick --engine edge --voice ar-SA-HamedNeural

# Preview & Compare (iteration tools)
audioformation preview MY_NOVEL ch01 --duration 30s
audioformation compare MY_NOVEL ch01 --engines edge,xtts

# Dry Run (estimation before committing)
audioformation run MY_NOVEL --all --dry-run
# Output: estimated time, chunk count, API calls, cloud cost

# Dashboard
audioformation serve

# Full Pipeline
audioformation run MY_NOVEL --all
audioformation run MY_NOVEL --from generate

### Command Details
Command	Purpose
preview	Generate first 30s (default) of a chapter with current settings. Essential for voice iteration
compare	A/B generate same text with different engines → outputs to 03_GENERATED/compare/ for listening
--dry-run	Estimate time, chunks, API calls, cost. No generation. Uses current project.json to calculate
echo ... | quick	Stdin support for scripting and quick tests

## project.json Schema (Core)

```json
{
  "id": "MY_NOVEL_2026",
  "version": "1.0",
  "created": "2026-02-12T23:30:00Z",
  "languages": ["ar", "en"],

  "chapters": [
    {
      "id": "ch01",
      "title": "المقدمة",
      "language": "ar",
      "source": "01_TEXT/chapters/ch01.txt",
      "character": "narrator",
      "direction": {
        "energy": "quiet contemplation",
        "pace": "slow, deliberate",
        "emotion": "wonder"
      }
    }
  ],

  "characters": {
    "narrator": {
      "name": "الراوي",
      "engine": "edge",
      "voice": "ar-SA-HamedNeural",
      "persona": "Calm authority, philosophical depth",
      "reference_audio": null
    },
    "hero": {
      "name": "البطل",
      "engine": "xtts",
      "voice": null,
      "persona": "Young, determined, searching",
      "reference_audio": "02_VOICES/references/hero.wav"
    }
  },

  "generation": {
    "fallback_scope": "chapter",  // ✅ Implemented (Item 2)
    "fallback_chain": ["edge", "gtts"],
    "chunk_max_chars": 200,
    "chunk_strategy": "breath_group",
    "crossfade_ms": 120,
    "crossfade_overrides": {      // ✅ Implemented (Item 4)
      "edge": 120,
      "xtts": 80,
      "gtts": 150
    },
    "crossfade_min_ms": 50,
    "leading_silence_ms": 100,
    "max_retries_per_chunk": 3,
    "fail_threshold_percent": 5,
    "xtts_temperature": 0.7,
    "xtts_repetition_penalty": 5.0,
    "edge_tts_rate_limit_ms": 200,
    "edge_tts_concurrency": 4,
    "edge_tts_ssml": true,
    "xtts_vram_management": "empty_cache_per_chapter"
  },

  "qc": {
  "snr_method": "vad_noise_floor",
  "snr_min_db": 20,
  "max_duration_deviation_percent": 30,
  "clipping_threshold_dbfs": -0.5,
  "lufs_deviation_max": 3,
  "pitch_jump_max_semitones": 12,
  "boundary_artifact_check": true
},

  "mix": {
    "master_volume": 0.9,
    "target_lufs": -16,
    "true_peak_limit_dbtp": -1.0,
    "gap_between_chapters_sec": 2.0,
    "ducking": {
      "method": "vad",
      "vad_model": "silero-vad",
      "vad_threshold": 0.5,
      "vad_threshold_ar": 0.45,
      "look_ahead_ms": 200,
      "attack_ms": 100,
      "release_ms": 500,
      "attenuation_db": -12,
      "frequency_aware": false
    }
  },

  "export": {
  "formats": ["mp3", "m4b"],
  "mp3_bitrate": 192,
  "m4b_aac_bitrate": 128,
  "include_cover_art": true,
  "cover_art": "00_CONFIG/cover.jpg",
  "chapter_transition": "silence",
  "chapter_transition_file": null,
  "metadata": {
    "author": "",
    "narrator": "",
    "publisher": "",
    "year": 2026,
    "description": ""
  }
 }
}
```

### Chapter Schema (Multi-Speaker Support)

Chapters support both single-narrator and multi-speaker dialogue.
Format is defined now. Single-narrator is Phase 1. Multi-speaker
parsing is Phase 2. Schema supports both from day one.

#### Single-Narrator Chapter (Phase 1)

```json
{
  "id": "ch01",
  "title": "المقدمة",
  "language": "ar",
  "source": "01_TEXT/chapters/ch01.txt",
  "character": "narrator",
  "mode": "single",
  "direction": {
    "energy": "quiet contemplation",
    "pace": "slow, deliberate",
    "emotion": "wonder"
  }
}
```
#### Multi-Speaker Chapter 
```json
{
  "id": "ch03",
  "title": "المواجهة",
  "language": "ar",
  "source": "01_TEXT/chapters/ch03.txt",
  "mode": "multi",
  "default_character": "narrator",
  "direction": {
    "energy": "building tension",
    "pace": "moderate, accelerating",
    "emotion": "confrontation"
  }
}
```

**Implementation Details:**
- **Per-segment character resolution**: Each `[speaker_id]` tag routes to specific character → engine → voice
- **Engine tracking**: Tracks all engines used per chapter for proper VRAM cleanup
- **Fallback handling**: Unknown characters fall back to chapter default engine
- **Backward compatibility**: Single mode chapters work unchanged
- **Text format**: Simple `[speaker_id]` tags on separate lines, blank lines revert to default

**Text Example:**
```text
قال الراوي بصوت هادئ.

[hero] لن أستسلم أبداً.

[villain] سنرى عن قرب.

عاد الراوي يكمل القصة.
```

## Arabic Text Processing Strategy

Arabic is the harder case and validates the entire pipeline. Treating it
as a first-class concern, not an afterthought.

### Diacritics (تشكيل)

Undiacritized Arabic is ambiguous — the same consonant skeleton can
represent multiple words with different pronunciations. TTS quality
depends heavily on correct diacritization.

- Strategy: Detect → Auto-diacritize → Allow manual override
```text
Pipeline:
├── 1. Detect diacritization level
│ Count diacritical marks / total characters
│ < 5% → "undiacritized" → auto-diacritize
│ > 30% → "diacritized" → pass through
│ 5-30% → "partial" → warn, offer auto-diacritize
│
├── 2. Auto-diacritize (when needed)
│ Primary: Mishkal (pip install mishkal)
│ ├── Lightweight, fast, pure Python
│ ├── Good for MSA (Modern Standard Arabic)
│ └── Sufficient for most literary Arabic
│ Fallback: CAMeL Tools (heavier, better disambiguation)
│ └── Only if Mishkal quality insufficient for project
│
├── 3. Store both versions
│ 01_TEXT/chapters/ch01.txt ← original
│ 01_TEXT/chapters/ch01.diacritized.txt ← processed
│ Generation uses .diacritized.txt
│ User can manually edit the diacritized version
│
└── 4. Validate gate checks:
• Diacritized file exists for each Arabic chapter
• Diacritization level > 30% in processed file
• Warn on any words that Mishkal flagged as ambiguous
```

### Mixed Arabic-English Text
- Strategy: Language-tagged segments within chunks
Detection:
├── Unicode block analysis per word
│ Arabic: U+0600–U+06FF, U+0750–U+077F, U+FB50–U+FDFF
│ Latin: U+0041–U+007A, U+00C0–U+024F
│
├── Tag each segment: [ar] or [en]
│
└── Chunk splitting respects language boundaries:
• Never split mid-word
• Prefer splitting at language transition points
• Short inline English (proper nouns, 1-3 words) stays in Arabic chunk
• Longer English passages get their own chunk with English voice

For edge-tts:
├── Arabic-primary voice handles short English inline (acceptable quality)
└── Switch voice for extended English passages (>10 words)

For XTTS:
├── Mid-sentence language switching is unreliable
└── Always split at language boundary for XTTS

### Dialect-Voice Matching
```text
project.json per-character field:

"narrator": {
"dialect": "msa", ← msa | eg | sa | ae | lb | ...
"voice": "ar-SA-HamedNeural"
}

Validate gate:
├── WARN if dialect=eg but voice=ar-SA-*
├── WARN if dialect=sa but voice=ar-EG-*
├── Does NOT block — user may intentionally cross-match
└── Informational only, logged in validation report

Dialect mapping for edge-tts voices:
├── msa → ar-SA-HamedNeural (best general MSA)
├── eg → ar-EG-SalmaNeural / ar-EG-ShakirNeural
├── ae → ar-AE-FatimaNeural / ar-AE-HamdanNeural
└── (extensible in engines.json)
```

### Implementation Location
src/audioformation/utils/arabic.py:
├── detect_diacritization_level(text) → float
├── auto_diacritize(text, engine="mishkal") → str
├── detect_language_segments(text) → List[Segment]
├── split_at_language_boundaries(text, max_chars) → List[Chunk]
└── validate_dialect_voice_match(dialect, voice) → Warning | None

### Inline Markup Format (in text files)
```text
قال له بصوت هادئ وهو ينظر إلى الأفق البعيد.

[hero] لن أستسلم أبداً. مهما كان الثمن.

[villain] سنرى ذلك. الوقت ليس في صالحك.

عاد الصمت يملأ المكان، ثقيلاً كغيمة رمادية.
```
#### Rules:
```text
Unmarked text → default_character
[character_id] at line start → switches speaker
Speaker persists until next tag or blank line
Blank line → revert to default_character
Tags must match character IDs in project.json
✅ BUILT: Parse tags → split into speaker segments
→ generate each segment with assigned character's voice
→ stitch in order with appropriate crossfade
→ proper VRAM cleanup for all engines used
```
#### Parser Location (✅ BUILT)
```text
src/audioformation/utils/text.py:
├── parse_chapter_segments(text, mode, default_char) → List[Segment]
│   Segment = { character: str, text: str, index: int }
├── chunk_segment(segment, max_chars, strategy) → List[Chunk]
└── validate_speaker_tags(text, known_characters) → List[Warning]

src/audioformation/generate.py:
├── _generate_chapter() → Per-segment character resolution
├── engines_used tracking → VRAM management for all engines
└── Fallback handling → Unknown characters → default engine
```
*This format is intentionally simple. No XML, no SSML in source
files. Just [speaker_id] on its own line. Easy to write,
easy to parse, easy to read in any text editor.*

### Pipeline Status Tracking (Chunk-Level Resumability)

`pipeline-status.json` tracks state at **chunk level** for Generate,
not just node level. If generation crashes at chapter 22, chunk 15,
it resumes from exactly there.

```json
{
  "project_id": "MY_NOVEL_2026",
  "nodes": {
    "bootstrap": { "status": "complete", "timestamp": "..." },
    "ingest": { "status": "complete", "timestamp": "..." },
    "validate": { "status": "complete", "timestamp": "..." },
    "generate": {
      "status": "partial",
      "engine": "xtts",
      "chapters": {
        "ch01": { "status": "complete", "chunks": 18, "duration_sec": 142.3 },
        "ch21": { "status": "complete", "chunks": 24, "duration_sec": 198.7 },
        "ch22": {
          "status": "partial",
          "chunks_done": 14,
          "chunks_total": 23,
          "last_chunk_file": "03_GENERATED/raw/ch22_014.wav",
          "error": "CUDA out of memory"
        }
      }
    },
    "qc_scan": { "status": "pending" },
    "process": { "status": "pending" },
    "compose": { "status": "skipped" },
    "mix": { "status": "pending" },
    "qc_final": { "status": "pending" },
    "export": { "status": "pending" }
  }
}
```
- Resume behavior:


Long audiobook runs (hundreds of chunks) cause PyTorch VRAM
fragmentation. Explicit management strategy:

Strategies (configurable in generation config):

"empty_cache_per_chapter" (default, recommended):
├── Keep model loaded for entire run
├── torch.cuda.empty_cache() between chapters
├── Good balance of speed vs stability
└── Works for most 4GB GPUs

"reload_periodic":
├── Unload and reload model every N chapters
├── Slower but prevents fragmentation on long runs
├── Fallback if empty_cache isn't sufficient
├── N configurable (default: 10)

"conservative":
├── Unload model after every chapter
├── Slowest but most stable
├── For systems with exactly 4GB and heavy OS VRAM usage
└── Auto-selected if available VRAM < 3.5GB

Auto-detection:
├── On bootstrap, measure available VRAM
├── > 6GB → "empty_cache_per_chapter"
├── 4-6GB → "empty_cache_per_chapter" (warn if < 4.5GB)
├── < 4GB → "conservative" + suggest CPU fallback
└── Store recommendation in 00_CONFIG/hardware.json

audioformation run MY_NOVEL --from generate checks pipeline-status.json
Skips chapters with "complete" status
Resumes partial chapters from chunks_done + 1
Re-validates completed chapters' output files exist (in case of file deletion)

#### Ducking Config

```json
"ducking": {
  "method": "vad",
  "vad_model": "silero-vad",
  "vad_threshold": 0.5,
  "vad_threshold_ar": 0.45,
  "look_ahead_ms": 200,
  "attack_ms": 100,
  "release_ms": 500,
  "attenuation_db": -12,
  "frequency_aware": false
}
```

- Per-language VAD threshold: Arabic speech has different energy
profiles (emphatic consonants, guttural sounds) than English.
Default 0.5 for English, 0.45 for Arabic. Pipeline reads chapter
language tag and selects appropriate threshold.

- Frequency-aware ducking (v1.1): Instead of reducing overall
music volume, apply a sidechain high-pass filter ducking only
200Hz–4kHz (speech band). Bass/sub-bass of ambient pads continues
at near-full volume. Set "frequency_aware": true to enable.
v1.0 uses simple gain ducking. v1.1 adds the filter approach.
Schema supports both now. Not using frequency-aware ducking by default.

## Implementation Phases

### Phase 1: Foundation + First Audio Output 
Status:  - All deliverables implemented, 218/218 tests passing (at Phase 1 completion)

├── Project scaffolding (CLI: new, list, status)
├── project.json schema + validation (jsonschema)
├── Folder structure creation (00_CONFIG through 07_EXPORT)
├── Hardware detection (GPU name, VRAM, CUDA availability)
├── Text ingestion (plain text + encoding detection)
├── Edge TTS integration (generate per-chapter)
├── LUFS measurement on every generated file (pyloudnorm)
├── Basic QC scan (SNR, clipping, duration sanity)
├── qc_report.json output
├── MP3 export (pydub + ffmpeg)
├── pytest setup with fixtures
├── Test with Arabic text FIRST (harder case validates easier)
├── gTTS fallback engine integration
├── edge-tts v7 upgrade for DRM token fix
└── Engine fallback chain (edge-tts → gTTS)

### Phase 2: XTTS + Characters + Processing
Status: **Completed** 
Deliverable: Voice-cloned narration with consistent quality

├── ✅ XTTS v2 integration (coqui-tts, Idiap fork)
├── ✅ Aggressive chunking (breath-group strategy)
├── ✅ Character profile system (JSON-driven)
├── ✅ Voice cloning workflow (reference audio → XTTS)
├── ✅ Cloud API adapter (httpx, abstract interface)
├── ✅ Crossfade stitching (Smart overrides: Edge 120ms, XTTS 80ms)
├── ✅ Engine fallback scope (Per-chapter logic implemented)
├── ✅ Arabic diacritics preprocessing (Mishkal integration)
├── ✅ Multi-speaker dialogue (per-segment character resolution)
├── ✅ Ambient pad generator (Numpy synthesis, mood presets)
├── ✅ Batch normalization (ffmpeg loudnorm filter)
└── ✅ Per-chunk retry logic on QC failure

### Phase 3: Mix + Export + Dashboard
Status: **Completed** All deliverables implemented, 371/371 tests passing 
Deliverable: Full audiobook with chapters, mixed and exported

├── ✅ Ambient pad generator (numpy synthesis, mood presets)
├── ✅ Music/SFX import + catalog
├── ✅ Multi-track mixer (voice + music layers)
├── ✅ VAD-based ducking (silero-vad trigger + gain envelope)
├── ✅ Chapter assembly (ordered concatenation)
├── ✅ QC Final gate (LUFS, true-peak, gaps, clipping)
├── ✅ M4B export (ffmpeg + ffmetadata chapters)
├── ✅ Cover art + ID3 metadata (mutagen)
├── ✅ Manifest with SHA256 checksums
├── ✅ FastAPI server + REST endpoints
├── ✅ Web dashboard (vanilla HTML/JS, project browser + timeline)
└── ✅ Full test suite + documentation
**Dashboard: Timeline View**
Integrated `wavesurfer.js` for mix timeline.
Single dependency, gives interactive waveform display, makes the
mix step dramatically more intuitive than abstract timeline blocks.
Dashboard tabs:
├── Projects (list, create, status overview)
├── Editor (project.json, text files)
├── Timeline (wavesurfer.js waveform per track)
├── Mix (volume sliders, ducking preview, layer toggle)
└── Export (format selection, cover art preview, progress)

### Phase 4: Polish + Distribution
Status: **In Progress**

Completed:
├── ✅ Dashboard v2 (all 6 sub-phases: 4a–4f)
├── ✅ Export view + download links
├── ✅ QC dashboard (basic list view)
├── ✅ Cast panel + engine/voice dropdowns
├── ✅ Direction dropdowns (SSML-mapped)
├── ✅ Pipeline stepper + hardware panel
├── ✅ Mix controls (ducking params)
├── ✅ "Run From" dropdown (resume from any step)
├── ✅ Assets tab (SFX + Music generation)
└── ✅ First M4B audiobook export verified

Remaining:
├── Server test coverage (routes.py: 0% → 60%+)
├── Cast UI engine adaptation (hide/show per engine type)
├── Console 404 noise suppression
├── PyInstaller packaging (.exe)
└── Loco-Tunes integration (ComposeEngine Tier 3 — separate app, file-system handshake)

### Handover Document Structure
```text
audioformation/
├── README.md
├── ARCHITECTURE.md
├── BUILD_LOG.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── pyproject.toml
│
├── src/audioformation/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── project.py
│   ├── pipeline.py
│   ├── validation.py
│   ├── ingest.py
│   ├── generate.py
│   ├── mix.py
│   │
│   ├── engines/
│   │   ├── base.py            # Abstract engine interface
│   │   ├── registry.py        # Engine discovery + fallback
│   │   ├── edge_tts.py        # + SSML direction mapping
│   │   ├── gtts_engine.py     # Emergency fallback
│   │   ├── xtts.py            # Voice cloning + VRAM management
│   │   ├── elevenlabs.py      # Cloud premium TTS
│   │   └── cloud.py           # Generic cloud adapter
│   │
│   ├── audio/
│   │   ├── processor.py       # Normalize, trim, LUFS, batch process
│   │   ├── mixer.py           # Multi-track + VAD ducking
│   │   ├── composer.py        # Ambient pad generator (5 presets)
│   │   ├── sfx.py             # Procedural SFX (whoosh, impact, click, drone)
│   │   └── synthesis.py       # Low-level oscillator/noise primitives
│   │
│   ├── qc/
│   │   ├── scanner.py         # Per-chunk QC (Node 3.5)
│   │   ├── final.py           # Final mix QC (Node 7)
│   │   └── report.py          # qc_report.json generation
│   │
│   ├── export/
│   │   ├── mp3.py             # MP3/WAV export
│   │   ├── m4b.py             # M4B + ffmetadata + cover art
│   │   └── metadata.py        # Manifest + SHA256 checksums
│   │
│   ├── server/
│   │   ├── app.py             # FastAPI entry + static mounts
│   │   ├── routes.py          # 15 REST endpoints
│   │   └── static/            # Dashboard HTML/JS/CSS
│   │
│   └── utils/
│       ├── arabic.py          # Diacritics, language detection, Mishkal
│       ├── text.py            # Chunking, speaker tags, splitting
│       ├── hardware.py        # GPU/VRAM detection + strategy
│       └── security.py        # Sanitization, path validation
│
├── tests/                     # 371 tests, 26 test files
│   ├── conftest.py
│   ├── test_arabic.py
│   ├── test_chunking.py
│   ├── test_cli_cast.py
│   ├── test_cli_compose.py
│   ├── test_cli_mix.py
│   ├── test_cli_preview.py
│   ├── test_composer.py
│   ├── test_engines.py
│   ├── test_export.py
│   ├── test_export_m4b.py
│   ├── test_ingest.py
│   ├── test_mix_unit.py
│   ├── test_mixer.py
│   ├── test_multispeaker.py
│   ├── test_pipeline.py
│   ├── test_processor.py
│   ├── test_project.py
│   ├── test_qc.py
│   ├── test_qc_final.py
│   ├── test_security.py
│   ├── test_server.py
│   ├── test_sfx.py
│   ├── test_validation.py
│   └── test_xtts.py
│
├── schemas/
│   └── project.schema.json
│
└── docs/
```

### Future Engine Candidates (Monitor, Not Adopted Yet)

| Engine | Promise | Status Feb 2026 | Action |
|---|---|---|---|
| FishAudio-S1 | Strong multilingual cloning + emotion | Promising, not mature | Test in Phase 4 |
| IndexTTS | XTTS successor candidate, better naturalness | Paper stage, limited adoption | Monitor |
| MeloTTS | Fast CPU inference, multilingual | Weaker voice cloning | Skip unless cloning not needed |
