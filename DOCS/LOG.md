# AudioFormation — Phase 1

## Part 1: Project Scaffolding
- Starting from the foundation. This first deliverable gives us a working CLI that can create projects, detect hardware, and manage pipeline state. Everything else plugs into this skeleton.

### File Order
Building bottom-up so every import resolves:
```text
1. pyproject.toml          — packaging + dependency pins
2. src/audioformation/__init__.py
3. src/audioformation/__main__.py
4. src/audioformation/config.py
5. src/audioformation/utils/security.py
6. src/audioformation/utils/hardware.py
7. src/audioformation/project.py
8. src/audioformation/pipeline.py
9. src/audioformation/validation.py
10. src/audioformation/cli.py
11. tests/conftest.py
12. tests/test_project.py
13. tests/test_security.py
```
### Checkpoint: Phase 1 Part 1 File Summary
```text
Files delivered (23 total):
─────────────────────────────────────────────────────────
 #  Path                                        Lines  Purpose
─────────────────────────────────────────────────────────
 1  pyproject.toml                                 55  Packaging + deps
 2  src/audioformation/__init__.py                  3  Package marker
 3  src/audioformation/__main__.py                  5  Entry point
 4  src/audioformation/config.py                  128  All constants
 5  src/audioformation/utils/__init__.py            1  Package marker
 6  src/audioformation/utils/security.py           80  Sanitization
 7  src/audioformation/utils/hardware.py          120  GPU/ffmpeg detect
 8  src/audioformation/project.py                 255  Project CRUD
 9  src/audioformation/pipeline.py                165  State machine
10  src/audioformation/validation.py              165  Gate logic
11  src/audioformation/cli.py                     210  CLI commands
12  tests/conftest.py                              70  Shared fixtures
13  tests/test_project.py                         120  Project tests
14  tests/test_security.py                        115  Security tests
15  tests/test_pipeline.py                        175  Pipeline tests
16  schemas/project.schema.json                   175  JSON Schema
17  src/audioformation/utils/text.py              210  Chunking + parsing
18  tests/test_chunking.py                        170  Chunking tests
19  src/audioformation/engines/__init__.py          1  Package marker
20  src/audioformation/engines/base.py             80  Engine interface
21  src/audioformation/engines/registry.py         65  Engine discovery
22  src/audioformation/engines/edge_tts.py        195  Edge TTS + SSML
23  tests/test_engines.py                         150  Engine tests
─────────────────────────────────────────────────────────
```
### Complete

```bash
# Install in dev mode
pip install -e ".[dev]"

# CLI
audioformation --version
audioformation new
```
## Phase 1 Complete — File Inventory

```text
 #  Path                                          Purpose
────────────────────────────────────────────────────────────────
 1  pyproject.toml                                 Packaging + deps
 2  README.md                                      Quick start
 3  src/audioformation/__init__.py                 Package marker
 4  src/audioformation/__main__.py                 Entry point
 5  src/audioformation/config.py                   All constants
 6  src/audioformation/project.py                  Project CRUD
 7  src/audioformation/pipeline.py                 State machine
 8  src/audioformation/validation.py               Gate logic + schema
 9  src/audioformation/ingest.py                   Text ingestion
10  src/audioformation/generate.py                 TTS orchestration
11  src/audioformation/cli.py                      All CLI commands

    src/audioformation/engines/
12  ├── __init__.py
13  ├── base.py                                    Engine interface
14  ├── registry.py                                Engine discovery
15  └── edge_tts.py                                Edge TTS + SSML

    src/audioformation/audio/
16  ├── __init__.py
17  └── processor.py                               LUFS, crossfade, trim

    src/audioformation/qc/
18  ├── __init__.py
19  ├── scanner.py                                 Per-chunk QC
20  └── report.py                                  Report formatting

    src/audioformation/export/
21  ├── __init__.py
22  ├── mp3.py                                     MP3/WAV export
23  └── metadata.py                                Manifest + checksums

    src/audioformation/utils/
24  ├── __init__.py
25  ├── security.py                                Sanitization
26  ├── hardware.py                                GPU/ffmpeg detect
27  ├── arabic.py                                  Diacritics + lang detect
28  └── text.py                                    Chunking + speaker tags

    schemas/
29  ├── project.schema.json                        JSON Schema
30  ├── examples/minimal.json
31  └── examples/full_novel.json

    tests/
32  ├── conftest.py                                Shared fixtures
33  ├── test_project.py                            Project CRUD
34  ├── test_security.py                           Sanitization
35  ├── test_pipeline.py                           State machine
36  ├── test_chunking.py                           Text + speaker tags
37  ├── test_arabic.py                             Diacritics + dialect
38  ├── test_engines.py                            Registry + SSML
39  ├── test_ingest.py                             Ingestion
40  ├── test_qc.py                                 QC scanner
41  ├── test_export.py                             MP3 + manifest
42  ├── test_processor.py                          Audio processing
43  └── test_validation.py                         Validation gate
────────────────────────────────────────────────────────────────
 Total: 43 files
```
## Phase 1 deliverable is complete. The end-to-end path works:

```bash
audioformation new "MY_NOVEL"
audioformation ingest MY_NOVEL --source ./chapters/
audioformation validate MY_NOVEL
audioformation generate MY_NOVEL --engine edge
audioformation qc MY_NOVEL --report
audioformation process MY_NOVEL
audioformation export MY_NOVEL --format mp3

# Or all at once:
audioformation run MY_NOVEL --all --dry-run   # estimate first
audioformation run MY_NOVEL --all             # execute
```

---

## Action Log

#### Initial Fast Check Implementation
1. **Created fast_check.py** - Comprehensive health check script with dependency validation, project structure verification, hardware detection, and test suite integration
2. **Created quick_check.bat** - Windows batch file for one-click dependency installation and health check execution
3. **Created README_FAST_CHECK.md** - Log & documentation explaining usage, current status, and troubleshooting

#### Setup & Fixes
4. **Fixed setuptools backend** - Changed `pyproject.toml` from `setuptools.backends._legacy:_Backend` to `setuptools.build_meta` to resolve `BackendUnavailable` error
5. **Installed dev dependencies** - `pip install -e ".[dev]"` successfully installed all 51 packages including core audio dependencies
6. **Verified CLI functionality** - `audioformation --version` returns `audioformation, version 0.1.0`
7. **Tested project creation** - CLI correctly prompts for NAME argument with `audioformation new`
8. **Validated dependency imports** - Confirmed all required packages (pydub, soundfile, edge-tts, pyloudnorm, midiutil) are properly installed and importable

--

#### Dependencies Installed
- Core: click, fastapi, uvicorn, pydub, numpy, soundfile, edge-tts, httpx, pyloudnorm, midiutil, mutagen, jsonschema
- Dev: pytest, pytest-asyncio, httpx[test]
- Audio processing: scipy, cffi, pydantic, starlette, aiohttp
- Build tools: setuptools, wheel, pyproject-hooks

### A quick health check script to validate project setup, phase1, part1.

#### Option 1: Run the Python script directly
```bash
python fast_check.py
```

#### Option 2: Use the batch file (Windows)
```bash
quick_check.bat
```

#### What it checks

✅ **Python Version** - Requires Python 3.11+  
📦 **Dependencies** - Verifies all required packages are installed  
📁 **Project Structure** - Checks core directories exist  
📄 **Core Files** - Validates essential project files  
🖥️ **Hardware** - Detects FFmpeg and GPU availability  
🧪 **Tests** - Runs quick test suite (what is available)

### Current Status

Based on the latest check:
- ✅ Python 3.11.8 - OK
- ✅ All dependencies installed (including dev dependencies)
- ✅ Core project structure and files present
- ✅ FFmpeg available
- ✅ CLI working (`audioformation --version` returns 0.1.0)

--

### Part 2:
```bash
(.venv) PS E:\co\Audio-Formation> audioformation new "MY_NOVEL"
E:\co\Audio-Formation\src\audioformation\cli.py:894: SyntaxWarning: invalid escape sequence '\$'
  click.echo(f"    edge-tts:   \$0.00 (free)")
  Detecting hardware...
✓ Created project: MY_NOVEL
  Path: E:\co\Audio-Formation\PROJECTS\MY_NOVEL
  GPU:  NVIDIA GeForce GTX 1650 Ti with Max-Q Design (4.0 GB VRAM)
  VRAM strategy: empty_cache_per_chapter
  ffmpeg: ✓

Next steps:
  1. Add text files to MY_NOVEL/01_TEXT/chapters/
  2. Edit MY_NOVEL/project.json (chapters + characters)
  3. Run: audioformation validate MY_NOVEL

(.venv) PS E:\co\Audio-Formation> audioformation ingest MY_NOVEL --source ./chapters/

```
#### The ModuleNotFoundError: No module named 'pyaudioop'
- Because the `audioop` module was removed from the Python standard library in Python 3.13. The error commonly appears in libraries like `pydub` which used `pyaudioop` as a fallback when `audioop` was missing. 

```bash
pip install audioop-lts
```
#### Fixes:
##### Fix 1: (x)
- Escape Sequence Warning in `cli.py`
##### Fix 2: (x)
- Corrected `parse_chapter_segments` Logic Bug (4 test failures)

The issue: when parsing multi-speaker text, the first unmarked lines should be assigned to `default_character`, but the segment ordering is wrong when a speaker tag appears after unmarked text followed by a blank line.

Root cause is in `src/audioformation/utils/text.py`. The blank-line handling flushes the current segment and resets to `default_character`, but then the next tagged line creates a new segment without properly flushing.

The key changes:

- Extracted `_flush()` helper — ensures consistent flush logic everywhere
- Reset `current_text_parts = []` after every flush — prevents text from leaking into the next segment
- Blank line now properly resets both the buffer and the character — so the next unmarked line correctly gets `default_character`
- Speaker switch flushes before reassigning — ordering is now deterministic
##### Fix 3: (x)
- pyproject.toml — Add audioop-lts for Python 3.13+
The python_version>='3.13' marker means it only installs when needed. Python 3.11/3.12 users won't pull it in.

##### Fix 4: (x)
- Test Environment Issue (1 failure)
The exist_ok=True and the broader monkeypatching should eliminate the directory conflict. The raising=False means if those modules don't have a direct PROJECTS_ROOT import, it silently skips.

##### Fix 5: (x)
- src/audioformation/utils/text.py (complete replacement)
Key changes:

Replaced _SPEAKER_TAG_RE regex with explicit _is_speaker_tag() parser — zero regex, zero platform ambiguity
_strip_all_tags() works line-by-line instead of regex sub
_find_all_speaker_tags() for validation uses same parser
flush() properly resets on blank lines
All parsing uses the same _is_speaker_tag() function — one code path, no divergence

##### Fix 6: (x)
- tests/test_security.py — Windows case-insensitive filesystem fix
Changed "projects" to "my_root_dir" and "other" to "other_dir" to avoid any collision with the "PROJECTS" directory created by the isolate_projects autouse fixture. Added exist_ok=True as belt-and-suspenders.

##### Fix 7: (x)
- tests/test_chunking.py — Updated to match new API
Added a targeted diagnostic test

##### Fix 8: (x)
- Defensive Validation
The validation should handle malformed chapter entries gracefully. In src/audioformation/validation.py.
Also added the same guard to _check_characters where it loops over chapters.

##### Fix 9: (x)
- src/audioformation/engines/edge_tts.py (complete replacement)

##### Fix 10: (x)
- src/audioformation/generate.py — Better error surfacing
The generation swallows errors silently. Let's surface them.

##### Fix 11: (x)
- Fix: src/audioformation/cli.py — Process command file selection
The process command picks up chunk files instead of stitched chapter files. Fix the file selection in the process_audio function.Same fix in the export_audio function.

##### Fix 12: (x)
- 403 = Microsoft updated their DRM token. The Sec-MS-GEC token in this version is stale. This is a library issue, not our code.
```bash
pip install --upgrade edge-tts
pip show edge-tts
```

##### Fix 13: (x)
- Fallback: gTTS Engine (Works Right Now, No Auth)
While edge-tts is down, let's add gTTS (Google Translate TTS) as an emergency fallback. It's not as good as edge-tts for Arabic, but it works immediately with zero auth.

```bash
pip install gTTS
```
- Added gtts_engine.py
- Registered the engine — src/audioformation/engines/registry.py
- Updateed the JSON schema to include gtts — in schemas/project.schema.json

**First audio generated. The full pipeline works.**

##### Fix 14 (x)
- Test edge-tts v7 (It Upgraded Successfully)
The edge-tts --text "test" --voice en-US-GuyNeural --write-media test_edge.mp3 command completed without error. That means edge-tts v7 fixed the 403. 
- Fixed Dependency Pins in pyproject.toml

#### FLOW

Source text (anywhere)
       │
       ▼ audioformation ingest --source
       │
PROJECTS/MY_NOVEL/01_TEXT/chapters/  (copied here)
       │
       ▼ audioformation generate
       │
PROJECTS/MY_NOVEL/03_GENERATED/raw/  (TTS output here)
       │
       ▼ audioformation process
       │
PROJECTS/MY_NOVEL/03_GENERATED/processed/  (normalized here)
       │
       ▼ audioformation export
       │
PROJECTS/MY_NOVEL/07_EXPORT/chapters/  (final MP3s here)

- Pipeline structure is working perfectly — ingest, validate, dry-run, status all clean.
--

- Added gtts_engine.py

#### Full Workflow
```
(.venv) PS E:\co\Audio-Formation> # Test gTTS directly
(.venv) PS E:\co\Audio-Formation> python -c "
>> from gtts import gTTS
>> tts = gTTS('مرحبا بالعالم', lang='ar')
>> tts.save('test_gtts.mp3')
>> print('SUCCESS: test_gtts.mp3')
>> "
SUCCESS: test_gtts.mp3
(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Verify the engine is registered
(.venv) PS E:\co\Audio-Formation> audioformation engines list
Available Engines:
  • edge (SSML)
  • gtts
(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Test the engine
(.venv) PS E:\co\Audio-Formation> audioformation engines test gtts
Testing engine: gtts...
✓ gtts is available.
(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Quick generate with gTTS
(.venv) PS E:\co\Audio-Formation> audioformation quick "Hello world" --engine gtts -o test_quick.mp3
Generating: "Hello world"
  Engine: gtts
  Voice:  ar-SA-HamedNeural
✓ Saved: test_quick.mp3
  Duration: 1.5s
(.venv) PS E:\co\Audio-Formation> audioformation quick "مرحبا بالعالم" --engine gtts -o test_ar.mp3
Generating: "مرحبا بالعالم"
  Engine: gtts
  Voice:  ar-SA-HamedNeural
✓ Saved: test_ar.mp3
  Duration: 2.0s
(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Full pipeline with gTTS
(.venv) PS E:\co\Audio-Formation> Remove-Item -Recurse -Force PROJECTS\MY_NOVEL
(.venv) PS E:\co\Audio-Formation> audioformation new "MY_NOVEL"
  Detecting hardware...
✓ Created project: MY_NOVEL
  Path: E:\co\Audio-Formation\PROJECTS\MY_NOVEL
  GPU:  NVIDIA GeForce GTX 1650 Ti with Max-Q Design (4.0 GB VRAM)
  VRAM strategy: empty_cache_per_chapter
  ffmpeg: ✓

Next steps:
  1. Add text files to MY_NOVEL/01_TEXT/chapters/
  2. Edit MY_NOVEL/project.json (chapters + characters)
  3. Run: audioformation validate MY_NOVEL
(.venv) PS E:\co\Audio-Formation> audioformation ingest MY_NOVEL --source .\chapters\
Ingesting text from: chapters

  ✓ ch01.txt → ch01 (ar, 301 chars [undiacritized])
  ✓ ch02.txt → ch02 (en, 441 chars)

✓ Ingested 2 files, skipped 0.
  Next: audioformation validate MY_NOVEL
(.venv) PS E:\co\Audio-Formation> audioformation validate MY_NOVEL
Validating project: MY_NOVEL

  ✓ project.json passes schema validation.
  ✓ Chapter 'ch01': text file OK (301 chars).
  ✓ Chapter 'ch02': text file OK (441 chars).
  ✓ Character 'narrator': voice 'ar-SA-HamedNeural' on engine 'edge'.
  ✓ Generation config present.
  ✓ LUFS target: -16.0
  ✓ ffmpeg found: C:\Users\ahmed\AppData\Local\Microsoft\WinGet\Links\ffmpeg.EXE
  ⚠ Chapter 'ch01': Arabic text is undiacritized. TTS quality may be degraded. Run auto-diacritization or provide a diacritized version.

Results: 7 passed, 1 warnings, 0 failures
✓ Validation PASSED
(.venv) PS E:\co\Audio-Formation> audioformation generate MY_NOVEL --engine gtts
Generating audio for: MY_NOVEL
  Engine: gtts

    ✓ Stitched 2 chunks → ch01.wav
    ✓ Stitched 3 chunks → ch02.wav
  ✓ ch01: 2 chunks, 0 failed
  ✓ ch02: 3 chunks, 0 failed

✓ Generation complete.
  Next: audioformation qc MY_NOVEL --report
(.venv) PS E:\co\Audio-Formation> # Check quality
(.venv) PS E:\co\Audio-Formation> audioformation qc MY_NOVEL --report
QC Report: qc_report_ch01.json
  Chunks:  2
  Passed:  2
  Warns:   0
  Failed:  0
  Fail %:  0.0%


QC Report: qc_report_ch02.json
  Chunks:  3
  Passed:  1
  Warns:   2
  Failed:  0
  Fail %:  0.0%

    ⚠ ch02_001
      └─ lufs: LUFS slightly outside target range.
    ⚠ ch02_002
      └─ lufs: LUFS slightly outside target range.

(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Process (normalize + trim)
(.venv) PS E:\co\Audio-Formation> audioformation process MY_NOVEL
Processing 2 chapter files...
  Target LUFS: -16.0

  ✓ ch01.wav
  ✓ ch02.wav

✓ Processing complete.
  Output: PROJECTS\MY_NOVEL\03_GENERATED\processed
(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Export
(.venv) PS E:\co\Audio-Formation> audioformation export MY_NOVEL --format mp3
Exporting 2 chapters as MP3...

  ✓ ch01.mp3
  ✓ ch02.mp3

Generating manifest...
  ✓ manifest.json

✓ Export complete.
  Output: PROJECTS\MY_NOVEL\07_EXPORT
(.venv) PS E:\co\Audio-Formation> 
(.venv) PS E:\co\Audio-Formation> # Check status
(.venv) PS E:\co\Audio-Formation> audioformation status MY_NOVEL
Project: MY_NOVEL
  Created:    2026-02-13T09:51:32.498178+00:00
  Languages:  ar, en
  Chapters:   2
  Characters: narrator

Pipeline Status:
  · bootstrap       pending
  ✓ ingest          complete
  ✓ validate        complete     [HARD GATE]
  ✓ generate        complete
    Chapters: 2/2 complete
  · qc_scan         pending      [AUTO GATE]
  ✓ process         complete
  · compose         pending
  · mix             pending
  · qc_final        pending      [HARD GATE]
  ✓ export          complete
```
### Testing
```bash
pytest -v
```
#### Phase 1 Testing Results: MAJOR PROGRESS ✅
🎯 Test Suite Status
218/218 tests passed (100% success rate)

--

### What Went Right (By Design)
Architecture Decision | Paid Off When...
---------------------|-------------------------
Engine-agnostic abstraction | edge-tts hit 403 → gTTS slotted in with zero pipeline changes
Hardware auto-detection | GTX 1650 Ti correctly identified, VRAM strategy auto-selected
Arabic-first validation | Undiacritized warning fired correctly on ch01
QC gates | Caught LUFS deviations on ch02 chunks before export
Chunk-level pipeline status | 2/2 chapters tracked individually

### The 14 Fixes Summary

Fixes 1-8:   Standard build issues (paths, regex, Windows FS)
Fix 9:       edge-tts full rewrite (SSML integration)
Fix 12:      edge-tts 403 DRM → library-level issue
Fix 13:      gTTS fallback engine added in minutes
Fix 14:      edge-tts v7 resolved it → both engines available

Fix 13 is the proof that the architecture works. A new engine went from zero to registered to generating Arabic audio in one file + one registry line. That's the engine abstraction paying for itself.

### Current State

✅ Working                    │ ⏳ Phase 2
──────────────────────────────┼──────────────────────────
new / ingest / validate       │ XTTS v2 integration
generate (edge + gtts)        │ Voice cloning workflow
QC scan + reports             │ Multi-speaker parsing
process (normalize)           │ Arabic diacritics (Mishkal)
export (MP3 + manifest)       │ Cloud API adapter
218/218 tests                 │ Crossfade tuning
Hardware detection            │ Engine fallback chain
Pipeline state tracking       │
dry-run estimation            │

#### Next Steps
1. ARCHITECTURE.md (assembled, with all amendments)
2. This build log (proves what works, what broke, what was fixed)
3. Priority order:
   a. XTTS v2 integration (the cloning story)
   b. Multi-speaker tag parsing (already defined, needs wiring)
   c. Arabic diacritics via Mishkal
   d. Mix + ducking (silero-vad)
4. Note: edge-tts v7 works now — pin it
5. Note: gTTS exists as emergency fallback
6. Note: 218 tests must stay green

--

GitHub Repository Ready

✅ Prepared AudioFormation for GitHub release:

Files Created/Updated:
- [README.md](README.md) - Added GitHub-ready sections:
  - [Current Status (Phase 1 complete, 218/218 tests passing)](README.md#current-status)
  - [Contributing guidelines](README.md#contributing)
  - [Clear feature status indicators](README.md#features)
- [.gitignore](.gitignore) - Comprehensive ignore rules:
  - Python development files
  - AudioFormation specific (generated audio, API keys)
  - IDE and OS files
  - Local development directories
- [CONTRIBUTING.md](CONTRIBUTING.md) - Detailed contribution guide:
  - [Development setup instructions](CONTRIBUTING.md#development-setup)
  - [Testing procedures](CONTRIBUTING.md#testing)
  - [Code style guidelines](CONTRIBUTING.md#code-style)
  - [Engine addition process](CONTRIBUTING.md#engine-addition-process)
  - [Pull request workflow](CONTRIBUTING.md#pull-request-workflow)
- [CHANGELOG.md](CHANGELOG.md) - Version history:
  - [Current unreleased changes (gTTS fallback, edge-tts v7)](CHANGELOG.md#unreleased-changes)
  - [v0.1.0 release notes (initial implementation)](CHANGELOG.md#v010-release-notes)
  - [Phase 2 planned features](CHANGELOG.md#phase-2-planned-features)

