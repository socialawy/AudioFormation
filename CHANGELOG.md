# Changelog

All notable changes to AudioFormation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-speaker dialogue support with per-segment character resolution
- Per-segment engine routing and voice assignment
- Engine tracking for VRAM management across multiple engines per chapter
- Fallback handling for unknown speaker tags to chapter default
- Comprehensive multi-speaker test suite (532 lines, 13 test classes)
- Enhanced VRAM management to handle multiple engines used in single chapter
- Backward compatibility for single-mode chapters
- Simple text format with `[speaker_id]` tags on separate lines
- XTTS v2 engine adapter with voice cloning support
- Reference audio path resolution against project directory
- XTTS generation parameters (temperature, repetition_penalty) with config overrides
- VRAM management strategies for GPU memory optimization
- Device auto-detection with CUDA availability and VRAM threshold checks
- Comprehensive XTTS test suite (389 lines, 13 test classes)
- Arabic locale support for XTTS (ar, ar-SA, ar-EG, ar-AE)
- CUDA out-of-memory error handling with specific error messages
- Generation count tracking for periodic model reloading
- gTTS emergency fallback engine for edge-tts failures
- Engine fallback chain (edge-tts → gTTS → cloud engines)
- Automatic retry with next engine on 403/500 errors
- Arabic diacritics detection and preprocessing
- Per-chunk QC scanning with SNR, clipping, and duration checks
- Defensive validation for malformed project.json entries
- File selection fixes in CLI process/export commands
- Ambient pad generation with mood presets
- Pipeline wiring for Items 1-8 complete
- ElevenLabs cloud TTS engine adapter (`engines/elevenlabs.py`)
- ElevenLabs auto-registration in engine registry (requires httpx)

### Changed
- **Dependencies:** pytest 8.0→<10, pytest-asyncio <1→<2, pre-commit <4→<5
- **Dependencies:** Moved `fastapi`, `uvicorn`, `midiutil` to optional dependency groups (`server`, `midi`)
- **Dependencies:** `mutagen` available in both core (export) and optional `m4b` group
- **Dependencies:** Added `cloud`, `server`, `m4b`, `midi` optional dependency groups
- Improved speaker tag parsing with per-segment character resolution
- Enhanced error reporting in generation
- Updated documentation to reflect multi-speaker implementation status
- Test coverage increased from 277 to 314 tests
- Reference audio resolution now uses project_path instead of bare Path
- Generation pipeline now supports XTTS-specific parameters
- Added VRAM management hooks after chapter stitching
- Enhanced VRAM management to iterate over all engines used per chapter
- Updated generation requests to use segment-specific voice and reference audio

### Fixed
- **QC Command:** Fixed `NameError: name 'all_reports' is not defined` in `qc` command
- **Chapter File Detection:** Fixed underscore filtering to properly distinguish chapter files from chunk files using numeric suffix check
- **SSML for Arabic:** Disabled SSML for edge-tts Arabic voices to prevent tags being read as text
- **torch CUDA Property:** Fixed `AttributeError` by using `total_memory` instead of `total_mem`
- FileExistsError in tests (added exist_ok=True)
- Invalid escape sequence warning in CLI
- File selection logic excluding chunk files
- Type checking for malformed chapter entries

### Removed
- **Duplicate `text.py`**: Removed root-level `src/audioformation/text.py` (duplicate of `utils/text.py`, not in architecture)

## [0.1.0] - 2026-02-13

### Added
- Initial AudioFormation pipeline implementation
- Project scaffolding and management
- Edge TTS integration with Arabic voice support
- SSML direction mapping for voice control
- Text chunking (breath-group strategy)
- LUFS measurement and normalization
- MP3 export with manifest generation
- Basic QC scanning and reporting
- Arabic text processing foundation
- CLI interface with all pipeline commands
- Comprehensive test suite (218/218 passing)

### Features
- **Core Pipeline**: Bootstrap → Ingest → Validate → Generate → QC → Process → Export
- **TTS Engines**: edge-tts (primary), gTTS (fallback)
- **Audio Processing**: LUFS normalization, silence trimming, QC scanning
- **Project Management**: JSON-driven configuration, pipeline status tracking
- **CLI Tools**: Project management, generation, processing, export commands
- **Testing**: Comprehensive test coverage with fixtures

### Architecture
- Five-domain architecture: VoxEngine (TTS), FXForge (SFX), ComposeEngine (Music), MixBus (Mixing), ShipIt (Export)
- JSON schema validation for project configuration
- Chunk-level resumability for long-running operations
- Security utilities for path validation and sanitization
- Modular design for easy engine extension

## Roadmap (Not Changelog Entries)

### Phase 2 — In Progress
- Cast CLI commands (`cast list`, `cast add`, `cast clone`)
- Wire `compose` CLI command to existing generator
- Cloud TTS adapters (OpenAI, Gemini — ElevenLabs ✅ done)
- `preview` and `compare` commands
- Decouple `click.echo()` from library code

### Phase 3 — Planned
- Multi-track mixer with VAD-based ducking
- M4B audiobook export with chapter markers
- QC Final gate (depends on mixer)
- FastAPI server + web dashboard
- FXForge (SFX domain)

### Phase 2 Completed
- XTTS v2 engine adapter with VRAM management ✅
- ElevenLabs cloud TTS adapter ✅
- Multi-speaker dialogue parsing and generation ✅
- Character profile routing via project.json ◐ (CLI workflow pending)
