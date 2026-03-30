## 2024-05-27 - Path Traversal Vulnerability Bypass via Symlinks
**Vulnerability:** Path validation logic (`validate_path_within`) in `src/audioformation/utils/security.py` used string-based checking (`os.path.abspath` and string prefixing) instead of filesystem-aware path resolution.
**Learning:** Pure string manipulation for path validation is vulnerable to bypass attacks, particularly through the use of symlinks, which can resolve to paths outside the intended root directory without triggering string-prefix failures.
**Prevention:** Always use `Path.resolve().is_relative_to()` for path containment checks. It resolves symlinks, normalizes paths, and securely verifies directory containment. Catch exceptions like `RuntimeError` to handle malformed paths or infinite symlink loops securely.
