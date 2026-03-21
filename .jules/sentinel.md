## 2024-05-24 - Symlink Path Traversal Bypass
**Vulnerability:** The `validate_path_within` function used string manipulation (`os.path.abspath`) which failed to resolve symlinks, allowing path traversal if a user could create a symlink within the root directory pointing to sensitive locations.
**Learning:** String-based path validation is insufficient against symlink attacks because `os.path.abspath` normalizes logical paths but doesn't resolve physical links.
**Prevention:** Always use `Path.resolve()` which resolves physical symlinks, followed by `is_relative_to()` for path validation checks.
