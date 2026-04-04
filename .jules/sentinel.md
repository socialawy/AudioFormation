## 2025-02-21 - Path Traversal in Mix Endpoint API Parameter
**Vulnerability:** The `/projects/{project_id}/mix` API endpoint in `src/audioformation/server/routes.py` accepted a `music` parameter (meant to specify a filename within the `05_MUSIC/generated` directory) but directly passed it to `mix_project` without sanitization. This allowed directory traversal payloads like `../../../etc/passwd` to be used for background music resolution.
**Learning:** Even internal API inputs that map strictly to filenames inside an expected directory must be sanitized. A simple check for file existence (`if not bg_music_path.exists():`) is insufficient as it confirms existence but allows looking outside the bounded directory.
**Prevention:** Always use established sanitization helpers (like `sanitize_filename`) or bound checks (like `validate_path_within`) for any user-supplied string that forms part of a filesystem path. Ensure bypass parameters like `FORCE_NO_MUSIC` are handled before and mutually exclusively from sanitization.

## 2025-02-22 - Static Files Protection Bypass
**Vulnerability:** `SafeStaticFiles` custom FastAPI handler was attempting to call `.lower()` on a `Path` object `p = Path(path).lower()`. A `PosixPath` object does not have a `.lower()` method. This raised an `AttributeError`, resulting in a 500 error instead of correctly applying the security block.
**Learning:** Security controls can be easily bypassed by runtime errors. While the vulnerability blocked access (via crash), a failed security control is always a risk, and it indicates the block code was never successfully hit in testing.
**Prevention:** Ensure string manipulation is performed on the string path itself before passing to `Path`, e.g. `Path(path.lower())`.
