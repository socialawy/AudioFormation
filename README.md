# 🏭 AudioFormation

**Production audio pipeline: Voice, SFX, Music, Mix, Export.**

Companion to VideoFormation (same architecture, different domain).

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Verify
audioformation --version
audioformation hardware

# Create a project
audioformation new "MY_NOVEL"

# Add text files
cp chapters/*.txt PROJECTS/MY_NOVEL/01_TEXT/chapters/

# Or ingest from a directory
audioformation ingest MY_NOVEL --source ./chapters/

# Validate
audioformation validate MY_NOVEL

# Generate audio (edge-tts with gTTS fallback)
audioformation generate MY_NOVEL --engine edge
# Falls back to gTTS automatically if edge-tts fails (403/500 errors)

# Check quality
audioformation qc MY_NOVEL --report

# Process (normalize + trim)
audioformation process MY_NOVEL

# Export
audioformation export MY_NOVEL --format mp3

# Or run the full pipeline
audioformation run MY_NOVEL --all
```

## Quick Generation (No Project)

```bash
# English
audioformation quick "Hello world" --voice en-US-GuyNeural -o hello.mp3

# Arabic
audioformation quick "مرحبا بالعالم" --voice ar-SA-HamedNeural -o hello_ar.mp3

# From stdin
echo "مرحبا" | audioformation quick --voice ar-SA-HamedNeural
```
## Requirements
Python 3.11+
ffmpeg on PATH
Optional: NVIDIA GPU with 4GB+ VRAM for XTTS voice cloning (Phase 2)

## Engine Support
- **edge-tts**: Free, excellent Arabic voices, upgraded to v7 for DRM compatibility
- **gTTS**: Emergency fallback, activates automatically on edge-tts failures
- **XTTS**: Local voice cloning (Phase 2, requires GPU)
- **Cloud engines**: ElevenLabs, OpenAI TTS (Phase 2, API keys required)

## Features
Feature | Status
-------|-------
Edge TTS (free, Arabic + English) | ✅ BUILT
SSML direction mapping | ✅ BUILT
Text chunking (breath-group) | ✅ BUILT
Per-chunk QC scanning | ✅ BUILT
LUFS normalization | ✅ BUILT
MP3 export with manifest | ✅ BUILT
Arabic diacritics detection | ✅ BUILT
Engine fallback chain (edge-tts → gTTS) | ✅ BUILT
gTTS emergency fallback | ✅ BUILT
XTTS voice cloning | ⏳ PHASE 2
Multi-speaker dialogue | ⏳ PHASE 2
Ambient pad generation | ✅ BUILT
VAD-based ducking | ⏳ PHASE 2
M4B audiobook export | ⏳ PHASE 2
Web dashboard | ⏳ PHASE 2

## Architecture
```text
audioformation CLI → FastAPI Server → Five Engines
                                      ├── VoxEngine (TTS)
                                      ├── FXForge (SFX)
                                      ├── ComposeEngine (Music)
                                      ├── MixBus (Mixing)
                                      └── ShipIt (Export)
```
- See ARCHITECTURE.md for the full planning document.

## Pipeline
```text
Bootstrap → Ingest → Validate → Generate → QC → Process → Compose → Mix → QC Final → Export
                      [GATE]                [AUTO]                          [GATE]
```
## Project Structure
- Each project lives under PROJECTS/ with a standard directory layout:
```text
PROJECTS/MY_NOVEL/
├── project.json           # Single source of truth
├── pipeline-status.json   # Execution state (chunk-level)
├── 00_CONFIG/             # Hardware, engines, characters
├── 01_TEXT/chapters/      # Source text files
├── 02_VOICES/references/  # Voice cloning samples
├── 03_GENERATED/          # TTS output (raw + processed)
├── 04_SFX/                # Sound effects
├── 05_MUSIC/              # Background music
├── 06_MIX/                # Mix sessions + renders
└── 07_EXPORT/             # Final MP3/M4B + manifest
```

## Testing
```bash
pip install -e ".[dev]"
pytest -v
```

## Current Status
- ✅ **Phase 1 Complete**: All core functionality implemented and tested (264/264 tests passing)
- ✅ **Engine Fallback**: edge-tts → gTTS automatic fallback for robust generation
- ✅ **Arabic Support**: Full Arabic text processing with diacritics detection
- ⏳ **Phase 2**: XTTS voice cloning, multi-speaker dialogue, advanced mixing

## Contributing
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
MIT
