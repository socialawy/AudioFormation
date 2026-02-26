## 2026-02-26 - [Path Traversal via Symlinks]
**Vulnerability:** `validate_path_within` used `os.path.abspath` which only performs lexical normalization, failing to resolve symbolic links. This allowed path traversal if a symlink inside the root pointed outside.
**Learning:** Lexical path validation is insufficient for security boundaries when symlinks are possible. Always resolve paths to their canonical form.
**Prevention:** Use `Path.resolve()` before validating path containment.
