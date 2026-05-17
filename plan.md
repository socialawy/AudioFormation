1. Modify `src/audioformation/utils/security.py` using `replace_with_git_merge_diff` to rewrite `validate_path_within` to use `Path.resolve().is_relative_to()` and catch `(TypeError, ValueError, RuntimeError, AttributeError, OSError)`.
2. Verify the changes to `src/audioformation/utils/security.py` by using `run_in_bash_session` with `cat src/audioformation/utils/security.py`.
3. Modify `src/audioformation/server/app.py` using `replace_with_git_merge_diff` to add `path is not None` check and `try...except` wrapper in `SafeStaticFiles.get_response` method.
4. Verify the changes to `src/audioformation/server/app.py` by using `run_in_bash_session` with `cat src/audioformation/server/app.py`.
5. Run the required tests by using `run_in_bash_session` with `uv run pytest tests/ -k 'not test_e2e_pipeline and not test_server and not test_xtts'`.
6. Run code style checks by using `run_in_bash_session` with `uv run ruff check` and `uv run ruff format`.
7. Update `.jules/sentinel.md` by using `run_in_bash_session` to run `cat << 'EOF' >> .jules/sentinel.md` with the new learning entry.
8. Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
9. Submit PR using the `submit` tool with branch name `sentinel-fix-path-traversal` and title `🛡️ Sentinel: [HIGH] Fix path traversal validation logic and SafeStaticFiles exceptions`.
