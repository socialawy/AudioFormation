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
2. Inherit from `BaseEngine` in `base.py`
3. Implement required methods:
   - `generate()`
   - `get_voices()`
   - `test_availability()`
4. Register engine in `registry.py`
5. Add tests in `tests/test_engines.py`

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

- ✅ **Phase 1**: Core pipeline, edge-tts, gTTS fallback, Arabic support
- ⏳ **Phase 2**: XTTS voice cloning, multi-speaker dialogue
- ⏳ **Phase 3**: Advanced mixing, ambient pads, M4B export

Focus contributions on Phase 2 features or bug fixes in Phase 1 functionality.
