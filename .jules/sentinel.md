## 2025-01-30 - Symlink-based Path Traversal Bypass
**Vulnerability:** Path traversal bypass in `validate_path_within` when validating whether a given path is inside a given root directory. It used `os.path.abspath(str(path))` and simple string prefix comparison.
**Learning:** `os.path.abspath` normalizes `..` and `.` but does *not* interact with the filesystem to resolve symbolic links. A malicious user could provide a symlink that points completely outside of `root`, and since string manipulation doesn't follow the symlink, it would pass the prefix check but operate outside the allowed directory.
**Prevention:** Use `Path.resolve().is_relative_to(root.resolve())` instead. `Path.resolve()` interacts with the OS to resolve all symlinks, computing the true canonical path before validation.
