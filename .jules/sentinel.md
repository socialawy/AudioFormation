## 2025-02-21 - Path Traversal in Mix Endpoint API Parameter
**Vulnerability:** The `/projects/{project_id}/mix` API endpoint in `src/audioformation/server/routes.py` accepted a `music` parameter (meant to specify a filename within the `05_MUSIC/generated` directory) but directly passed it to `mix_project` without sanitization. This allowed directory traversal payloads like `../../../etc/passwd` to be used for background music resolution.
**Learning:** Even internal API inputs that map strictly to filenames inside an expected directory must be sanitized. A simple check for file existence (`if not bg_music_path.exists():`) is insufficient as it confirms existence but allows looking outside the bounded directory.
**Prevention:** Always use established sanitization helpers (like `sanitize_filename`) or bound checks (like `validate_path_within`) for any user-supplied string that forms part of a filesystem path. Ensure bypass parameters like `FORCE_NO_MUSIC` are handled before and mutually exclusively from sanitization.
## 2025-02-23 - Broken Security Check in SafeStaticFiles
**Vulnerability:** The custom `SafeStaticFiles` middleware in `src/audioformation/server/app.py` intended to block access to sensitive directories (like `00_CONFIG` and `.git`). However, it used `p = Path(path).lower()`, which raises an `AttributeError` because `pathlib.Path` objects lack a `.lower()` method. This effectively broke static file serving entirely (causing 500 errors) and represented a malformed security check. If such errors were ever 'swallowed' without raising an HTTP exception, it could result in 'failing open' and allowing access to sensitive files.
**Learning:** Security checks that rely on path manipulation or normalization must be carefully tested for runtime exceptions. An unhandled exception in a security gate can either block legitimate traffic (Denial of Service) or, if caught improperly elsewhere, fail open. Always normalize the string representation of paths before converting them to `Path` objects.
**Prevention:** Thoroughly test security middleware endpoints for both valid and invalid access attempts. Ensure that path string normalizations like `.lower()` are applied directly to the string before instantiating `Path(str(path).lower())`.

## 2024-05-31 - Path Traversal Prevention bypass

**Vulnerability:** String-based path checks (`os.path.abspath(str(path)).startswith(os.path.abspath(str(root)))`) fail to resolve symlinks securely before validation, allowing directory traversal bypasses in functions designed to sandbox file operations.

**Learning:** `os.path.abspath` only normalizes paths but does not evaluate physical filesystem links. Malicious symlinks can point outside the intended root directory while their string representations still appear visually nested within it, bypassing simple string-matching prefixes.

**Prevention:** To securely validate paths against directory traversal, always resolve links completely using `Path.resolve()` on both the target path and the root, and then perform `Path.is_relative_to()`. Avoid any string manipulation for security path boundaries.
