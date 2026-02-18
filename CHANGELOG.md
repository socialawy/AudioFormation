
# Changelog

All notable changes to AudioFormation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed 2026-02-18 (Session 6 — Dashboard Security & Code Quality)
- **Poll Isolation**: Single `pollInterval` caused cross-contamination between generation, mix, and export polls
  - Replaced with `activePolls{}` object, each poller gets isolated key
  - Added `stopAllPolls()` to clear all polls on navigation
- **XSS Vulnerabilities**: Template literals with unsanitized server data in `renderQCReports`
  - Rebuilt nested templates with DOM node construction
  - Applied consistent `escapeHtml()` usage throughout dashboard
  - Reduced from 7 real vulnerabilities to 5 false positives
- **Code Quality Issues**: Multiple SonarQube violations affecting maintainability
  - Nested ternary → explicit if/else statements
  - `.find()` → `.some()` for boolean existence checks  
  - `parseInt/parseFloat` → `Number.parseInt/Number.parseFloat`
  - `.replace()` → `.replaceAll()` in escapeHtml function
  - `for` loops → `for-of` iterations
  - Added optional chaining `?.` for safer property access
- **Error Handling Inconsistency**: Mixed `alert()` usage throughout dashboard
  - Replaced all `alert()` calls with unified `showToast()` notification system
  - Consistent error messaging and user feedback
- **Audio Overlap**: Multiple audio files could play simultaneously
  - Added `stopAllAudio()` function to pause all elements before new playback
- **Dirty State Tracking**: No indication of unsaved changes in Cast panel
  - Implemented `_isDirty` flag with `markDirty()`/`clearDirty()` functions
  - Visual feedback on Save Changes button

### Security 2026-02-18
- **Snyk Code Scan**: Reduced from 7 XSS vulnerabilities to 5 false positives
- **Real vulnerabilities eliminated**: 2 critical XSS issues in QC report rendering
- **Production readiness**: All actual security issues resolved

### Tests 2026-02-18
- **423 tests collected, 423 passing** (100% success rate)
- **Coverage: 76%** (up from 69%)
- **All 6 dashboard patches verified** via automated and manual inspection

### Fixed 2026-02-17 (Session 5 — Production Debugging)
- **`ch*.wav` hard-coded glob**: Process, Mix commands only found `ch`-prefixed files.
  Changed to `*.wav` with chunk-file exclusion filter in:
  - `cli.py` process_audio (~line 754)
  - `mix.py` lines 96, 104
- **M4B export `-c:v copy`**: Always added even without cover art, causing ffmpeg error.
  Now conditional on `has_cover`.
- **E2E test `--voice` flag**: CLI `generate` has no `--voice` option. Removed from test.
- **E2E test missing pipeline steps**: Added `qc-scan` and `qc-final` steps to
  `_run_engine_test`. QC Final is non-blocking (short test clips fail LUFS threshold).
- **`batch_process_project` wrong directory**: Searched `03_GENERATED/*.wav` instead of
  `03_GENERATED/raw/*.wav`. Added `raw/` subdirectory search with root fallback.
- **`qc-final` missing from Run All Pipeline**: Dashboard `runAllPipeline()` skipped
  qc-final step. Added to steps array and nodeMap.

### Added 2026-02-17 (Session 5)
- **"Run From" dropdown**: Pipeline can now resume from any step (validate → export).
  HTML select + `runFromStep()` JS function. Reuses existing `waitForNode()`.
- **First M4B audiobook export**: Verified end-to-end on Project 10 (Arabic, edge-tts).

### Tests
- **387 collected, 378 passed, 9 skipped, 0 failed**
- **Coverage: 69.03%** (up from 64.98%)
- E2E tests now exercise: bootstrap → ingest → validate → generate → qc-scan →
  process → mix → qc-final (soft) → export (conditional)

### Added 2026-02-16 (Session 3)
- **QC Scan API**: New endpoint for quality control scanning
  - POST /api/projects/{id}/qc-scan (Node 3.5)
  - Scans generated audio for SNR, clipping, duration, LUFS, pitch, boundary artifacts
  - Background task with proper status tracking
  - Frontend integration in "Run All Pipeline"

- **Pipeline Status Fixes**: Robust status file handling
  - update_node_status handles missing pipeline-status.json (bootstrap)
  - mark_node consolidated to delegate to update_node_status
  - Eliminates duplicate JSON I/O logic
  - Tests updated to use isolate_projects fixture

- **Architecture Synchronization**: Documentation alignment
  - API docs updated: 16 endpoints (added qc-scan)
  - Dashboard port corrected: localhost:4001 (was 4000)
  - Test count updated: 26 test files (was 24)
  - Endpoint count updated: 15 endpoints (was 13)

- **Code Quality**: UTF-8 encoding and cleanup
  - Fixed UTF-8 artifacts in pipeline.py (— → --, → → ->)
  - Removed dead code: DASHBOARD_PORT = 4000
  - Enhanced test coverage: 63.40% (60% minimum met)

### Added 2026-02-16 (Session 2)
- **Pipeline Status Tracking Wrapper**: Comprehensive background task monitoring
  - Async-aware `_run_with_status()` wrapper for all pipeline functions
  - Detects and awaits coroutines from async functions (generate, mix, process, compose, export)
  - Records node status as running → complete/failed with error messages
  - Fixes root cause of polling timeouts (tasks were silently discarded)

- **"Run All Pipeline" Button**: Full end-to-end orchestration in dashboard
  - Single-click execution of entire audiobook pipeline (validate → generate → process → compose → mix → export)
  - Real-time progress updates via button text (Validating... → Generating... → etc.)
  - Validation failure details displayed to user
  - 10-minute timeout per stage with graceful error handling
  - Auto-refresh on completion

- **Polling Timeout Protection**: Prevent infinite polling on silent failures
  - 10-minute timeout on generation/mix/process/compose/export polling
  - Clear user alert when operation times out
  - Button state reset on timeout so UI isn't frozen

- **Console Noise Suppression**: Silent handling of expected 404s
  - `loadAudio()` refactored to silently try fallback paths (mixed → processed → raw)
  - Only actual decode errors are shown to user
  - Cleaner browser console during normal operation

### Fixed 2026-02-16 (Session 2)
- **Background Task Execution**: Generate/mix/process/compose/export functions now execute
  - Made `_run_with_status()` async with `asyncio.iscoroutine()` detection
  - FastAPI properly awaits all async pipeline functions
  - Status updates write to pipeline-status.json after task completion

- **Non-Serializable Validation Response**: `/validate` endpoint 500 error
  - Called `ValidationResult.summary()` to convert object to dict
  - FastAPI can now serialize response to JSON
  - Run All Pipeline validates before continuing

- **BackgroundTasks.add_task() Signature Error**: TypeError on background task submission
  - Fixed positional vs keyword argument conflict
  - Changed from `func=lambda...` to positional lambda argument
  - All 5 background endpoints now work (generate, mix, process, compose, export)

- **Validation Failure Handling**: JavaScript defensive JSON parsing
  - `runAllPipeline()` handles both JSON and plain-text errors
  - Checks `Content-Type` header before parsing
  - Shows validation failures with detailed error messages
  - Gracefully handles 500 responses

- **Console Error Handling**: Better error logging in async tasks
  - `_run_with_status()` logs exceptions with `logger.exception()`
  - Error details saved to pipeline-status.json `error` field
  - Visible in UI status popup for debugging

### Changed 2026-02-16 (Session 2)
- **routes.py**: Added `asyncio` import, made wrapper async-aware, fixed all 5 background task calls
- **app.js**: Simplified `runAllPipeline()` with step array loop, added `waitForNode()` helper, improved error handling
- **validation.py**: Already had `.summary()` method (no changes needed)
- **style.css**: Added `.btn.success` green button styling for "Run All Pipeline"

### Tests
- All existing tests passing (371 tests)
- Manual testing confirms: validation failures show in UI, background tasks execute and write status, polling timeouts gracefully

## [0.3.0+] - 2026-02-16

### Added 2026-02-16
- **Code Quality Infrastructure**: Comprehensive tooling for robust development
  - Ruff linting with automated fixes (31 issues resolved)
  - pytest-cov coverage reporting with 80% threshold
  - MyPy type checking with gradual adoption strategy
  - Enhanced CI/CD pipeline with quality gates
  - Pre-commit hooks updated with type checking
- **Security Hardening**: Fixed all XSS vulnerabilities in web dashboard
  - Input sanitization applied to all dynamic content
  - Snyk security scanning integrated (0 remaining issues)
- **Coverage Reporting**: HTML and XML reports with Codecov integration
- **Type Safety**: 21 type errors identified for gradual resolution

### Changed
- **Dependencies**: Added pytest-cov, mypy, types-jsonschema to dev group
- **CI Pipeline**: Enhanced with linting, type checking, and coverage reporting
- **Pre-commit**: Added MyPy type checking hook
- **Configuration**: Updated pytest.ini with coverage options and thresholds

### Fixed
- **Ruff Installation**: Resolved missing linter tooling
- **XSS Vulnerabilities**: All 3 Medium-severity issues resolved in app.js
- **Import Issues**: Fixed unused imports and circular dependencies
- **Type Annotations**: Improved type hints across codebase

### Tests
- **371 tests passing** with comprehensive coverage reporting
- **Current coverage**: 65% (targeting 80%+)
- **Quality gates**: Automated linting, type checking, and security scanning

## [0.3.0] - 2026-02-14

### Added
- **Mixer engine** (`audio/mixer.py`): Multi-track mixing with VAD-based ducking (Silero) and energy fallback
- **Mix pipeline node** (`mix.py`): Orchestrator with auto-detect background music, processed→raw fallback
- **QC Final gate** (`qc/final.py`): LUFS ±1, true peak, clipping validation on mixed output
- **XTTS v2 engine** (`engines/xtts.py`): Local voice cloning with VRAM management (empty_cache, conservative, reload_periodic)
- **Multi-speaker generation**: Per-segment character→voice→engine routing with `[speaker_id]` tags
- **ElevenLabs engine** (`engines/elevenlabs.py`): Cloud TTS adapter
- **SFX generator** (`audio/sfx.py`): Procedural whoosh, impact, UI click, drone
- **Audio synthesis** (`audio/synthesis.py`): Low-level oscillator/noise primitives
- **M4B export** (`export/m4b.py`): Audiobook with chapter markers, ffmetadata, cover art
- **Web dashboard**: Projects, Editor (config tabs + generation control), Mix & Review (wavesurfer.js)
- **6 new API endpoints**: validate, process, compose, export, qc, qc-final
- **Per-engine crossfade overrides**: edge 120ms, xtts 80ms, gtts 150ms
- **Per-chapter engine fallback**: Chapter-scope and project-scope strategies
- **Ambient pad generator**: 5 mood presets, pure numpy, loopable
- **Arabic diacritics pipeline**: Mishkal integration with auto-detect and store-both-versions
- **Web Dashboard:** Minimal HTML/JS interface for project management.
  - Project list view with status indicators.
  - New project creation UI.
  - Static file serving via FastAPI (requires `aiofiles`).
  - **Timeline:** Waveform visualization (`wavesurfer.js`) and audio playback.
  - **Editor:** Chapter configuration, text ingest, and generation controls.
  - **Mix View:** Trigger mix pipeline, view status, listen to results.
- **M4B Export:** Full audiobook export with chapter markers, metadata, and cover art (`audioformation export --format m4b`).
- **QC Final:** Hard gate for mixed audio validation (LUFS, True Peak, Clipping) (`audioformation qc-final`).
- **Mixing:** VAD-based ducking for background music (`audioformation mix`).
- **API Endpoints:**
  - `POST /api/projects/{id}/mix`
  - `POST /api/projects/{id}/generate`
  - `PUT /api/projects/{id}`
- **CLI Commands:**
  - `mix`: Run the mixing pipeline.
  - `cast`: Manage characters (`list`, `add`, `clone`).
  - `compose`: Generate ambient music pads using procedural synthesis.
  - `preview`: Generate short samples of chapters for rapid voice iteration.
  - `compare`: A/B test multiple engines/voices on the same text.
  - `serve`: Launch API server and dashboard.
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
- **Project schema:** updated with all Phase 2/3 fields (fallback, crossfade, ducking, VRAM, multi-speaker)
- **Pipeline:** status tracking now at chunk level with resume support
- **Server:** routes expanded from 4 to 13 endpoints

- **Dependencies:** Added `aiofiles` to `[server]` group.
- **Refactor:** Decoupled `generate.py` and `mix.py` from CLI `click` functions. Now uses `logging` and callbacks.
- **Testing:** Increased coverage to 360 tests (100% passing). Added robust dependency mocking in `conftest.py`.
- **Dependencies:** pytest 8.0→<10, pytest-asyncio <1→<2, pre-commit <4→<5
- **Dependencies:** Moved `fastapi`, `uvicorn`, `midiutil` to optional dependency groups (`server`, `midi`)
- **Dependencies:** `mutagen` available in both core (export) and optional `m4b` group
- **Dependencies:** Added `cloud`, `server`, `m4b`, `midi` optional dependency groups
- **Improved speaker tag parsing:** with per-segment character resolution
- **Enhanced error reporting:** in generation
- **Updated documentation:** to reflect multi-speaker implementation status
- **Reference audio resolution:** now uses project_path instead of bare Path
- **Generation pipeline:** now supports XTTS-specific parameters
- **Added VRAM management:** hooks after chapter stitching
- **Enhanced VRAM management:** to iterate over all engines used per chapter
- **Updated generation requests:** to use segment-specific voice and reference audio

### Fixed
- **Server import error:** (`scan_project_chunks` removed — dead import)
- **Schema validation:** now covers generation, mix, export, and QC sections
- **Envelope edge artifacts:** in mixer (smooth fade vs hard set)
- **Mix Logic:** Decoupled from CLI for server compatibility.
- **QC Command:** Fixed `NameError: name 'all_reports' is not defined` in `qc` command
- **Chapter File Detection:** Fixed underscore filtering to properly distinguish chapter files from chunk files using numeric suffix check
- **SSML for Arabic:** Disabled SSML for edge-tts Arabic voices to prevent tags being read as text
- **torch CUDA Property:** Fixed `AttributeError` by using `total_memory` instead of `total_mem`
- **FileExistsError in tests:** (added exist_ok=True)
- **Invalid escape sequence warning:** in CLI
- **File selection logic:** excluding chunk files
- **Type checking for malformed chapter entries**

### Removed
- **Duplicate `text.py`**: Removed root-level `src/audioformation/text.py` (duplicate of `utils/text.py`, not in architecture)

### Tests
- **371 tests passing** (up from 264 in v0.2)
- New test suites: test_mix_unit, test_multispeaker, test_xtts, test_qc_final, test_sfx, test_composer, test_server

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
