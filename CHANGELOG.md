# Changelog

All notable changes to AudioFormation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- Pipeline wiring for Items 1-6 complete

### Changed
- Upgraded edge-tts to v7 to resolve 403 DRM token errors
- Improved speaker tag parsing with explicit logic
- Enhanced error reporting in generation
- Updated documentation to reflect actual implementation status
- Test coverage increased from 264 to 277 tests
- Reference audio resolution now uses project_path instead of bare Path
- Generation pipeline now supports XTTS-specific parameters
- Added VRAM management hooks after chapter stitching

### Fixed
- FileExistsError in tests (added exist_ok=True)
- Invalid escape sequence warning in CLI
- File selection logic excluding chunk files
- Type checking for malformed chapter entries

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
- FastAPI server foundation
- Comprehensive test suite (218/218 passing)

### Features
- **Core Pipeline**: Bootstrap → Ingest → Validate → Generate → QC → Process → Export
- **TTS Engines**: edge-tts (primary), gTTS (fallback)
- **Audio Processing**: LUFS normalization, silence trimming, QC scanning
- **Project Management**: JSON-driven configuration, pipeline status tracking
- **CLI Tools**: Project management, generation, processing, export commands
- **Testing**: Comprehensive test coverage with fixtures

### Architecture
- Five-engine architecture: VoxEngine, FXForge, ComposeEngine, MixBus, ShipIt
- JSON schema validation for project configuration
- Chunk-level resumability for long-running operations
- Security utilities for path validation and sanitization
- Modular design for easy engine extension

## [Upcoming - Phase 2]

### Planned
- XTTS v2 integration for local voice cloning
- Multi-speaker dialogue parsing and generation
- Character profile system with voice assignments
- Advanced mixing with VAD-based ducking
- M4B audiobook export with chapter markers
- Web dashboard for project management
- Cloud engine support (ElevenLabs, OpenAI TTS)
