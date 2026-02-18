# Contributing to AudioFormation

Thank you for your interest in contributing to AudioFormation! This document provides guidelines for contributors.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/audioformation.git
   cd audioformation
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Verify installation**
   ```bash
   audioformation --version
   pytest -v
   ```

## Running Tests

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_engines.py -v

# Run with coverage
pytest --cov=audioformation --cov-report=html
```

## Code Style

This project follows standard Python conventions:
- Use `black` for code formatting
- Use `ruff` for linting
- Follow PEP 8 style guidelines

## Project Structure

```
src/audioformation/
├── engines/          # TTS engine implementations
├── utils/           # Utility functions (text, arabic, security)
├── audio/           # Audio processing (mixing, effects)
├── qc/              # Quality control and scanning
├── export/          # Export formats and metadata
└── server/          # FastAPI web interface
```

## Adding New TTS Engines

1. Create engine class in `src/audioformation/engines/`
2. Inherit from `TTSEngine` in `base.py`
3. Implement required properties and methods:
   - `name` (property)
   - `supports_cloning` (property)
   - `supports_ssml` (property)
   - `requires_gpu` (property)
   - `generate(request: GenerationRequest) -> GenerationResult`
   - `list_voices(language: str | None) -> list[dict]`
   - `test_connection() -> bool`
4. Register engine in `registry.py` (`_register_defaults()`)
5. Add tests in `tests/test_engines.py`
6. See `engines/elevenlabs.py` for a complete cloud adapter example

## Decoupling Library Code from CLI

The `generate.py` module currently uses `click.echo()` for progress reporting. Before Phase 3
(server work), this must be refactored to use standard logging or callbacks.

**Current Pattern (❌ Don't do this):**
```python
from click import echo
def generate_project(project_id: str):
    echo(f"Generating {project_id}...")  # Hardcoded CLI output
```

**Target Pattern (✅ Do this):**
```python
import logging
logger = logging.getLogger(__name__)

def generate_project(project_id: str, progress_callback=None):
    logger.info(f"Generating {project_id}...")
    if progress_callback:
        progress_callback(f"Generating {project_id}...")  # Optional, injectable
```

**Files to Update:**
- `src/audioformation/generate.py` — ~8 click.echo() calls (lines 131, 137, 145, 365, 372, 383, 391, 414, 419)

**Why This Matters:**
Allows the library to be used as a pure Python module in FastAPI servers, Jupyter notebooks,
and other non-CLI contexts without hardcoded terminal output.

**Review Checklist:**
- [ ] No `from click import *` in library code (only in `cli.py`)
- [ ] Core functions use `logging.info()` or optional callbacks
- [ ] Tests mock progress callbacks, not `click.echo()`
- [ ] CLI layer in `cli.py` can add pretty formatting (colors, progress bars) on top

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest -v`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## Pull Request Guidelines

- Include tests for new functionality
- Update documentation if needed
- Ensure all existing tests pass
- Follow the existing code style
- Provide a clear description of changes

## Issues

- Bug reports: Use GitHub Issues with detailed description
- Feature requests: Open an Issue with "Feature Request" label
- Questions: Use GitHub Discussions

## Current Development Status

- ✅ **Phase 1 Complete**: Core pipeline, edge-tts, gTTS fallback, Arabic support
- ✅ **Phase 2 Partial**: XTTS engine, ElevenLabs adapter, multi-speaker, ambient composer
- ⏳ **Phase 2 Remaining**: Cast CLI, compose CLI wiring, preview/compare commands
- ⏳ **Phase 3 Planned**: Mixer with ducking, M4B export, QC Final, web dashboard

Focus contributions on Phase 2 remaining items or bug fixes in existing functionality.
