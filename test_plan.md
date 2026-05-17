1. **Fix path validation in `src/audioformation/utils/security.py`**
   - Replace string-based manipulation (`os.path.abspath` and `startswith`) with strict `Path.resolve().is_relative_to()`.
   - Update the exception catching to handle `(TypeError, ValueError, RuntimeError, AttributeError, OSError)` to fail closed securely on malformed inputs.
2. **Hardening `SafeStaticFiles` in `src/audioformation/server/app.py`**
   - Explicitly validate that `path` is not None.
   - Wrap the path normalization in a `try...except` block, raising `HTTPException(status_code=400)` to ensure it fails closed securely on malformed inputs.
3. **Verify code changes**
   - Run `uv run pytest tests/` with the required flags to ensure no tests break.
   - Run `uv run ruff check` and `uv run ruff format` to ensure code style is maintained.
4. **Update `.jules/sentinel.md`**
   - Add a journal entry documenting the learning about replacing `os.path.abspath` checks with strict `Path.resolve()` for symlink handling, and failing closed on exceptions.
5. **Complete pre-commit steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
6. **Submit PR**
   - Submit the PR with the title `🛡️ Sentinel: [HIGH] Fix path traversal validation logic`.
