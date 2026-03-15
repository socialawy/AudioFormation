## 2024-03-15 - [Path Traversal bypass via symlinks]
**Vulnerability:** Path Traversal bypass via symlinks in `validate_path_within`.
**Learning:** String-based path manipulation like `os.path.abspath` does not resolve symlinks. This means a path like `root/symlink/secret.txt` will be deemed valid (starts with `root/`) even if `symlink` points entirely outside `root/`.
**Prevention:** To securely validate paths, always resolve symlinks first using `Path.resolve().is_relative_to(root.resolve())`. Catch exceptions like `RuntimeError` to gracefully handle malformed paths or infinite symlink loops.
