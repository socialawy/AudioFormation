## 2025-02-28 - [Path Traversal bypass via symlinks]
**Vulnerability:** Symlinks could be used to bypass directory traversal protections (`validate_path_within`), as the check relied only on string manipulation (`os.path.abspath`).
**Learning:** `os.path.abspath` normalizes '.' and '..' but does not resolve symlinks. A symlink pointing outside a directory will bypass path validation based solely on string prefixes, leading to potential path traversal and unintended file access.
**Prevention:** Always use `Path.resolve().is_relative_to(root.resolve())` instead of string-based path checking when validating that a file remains within a specific directory. Catch `RuntimeError` to gracefully fail on potential infinite symlink loops.
