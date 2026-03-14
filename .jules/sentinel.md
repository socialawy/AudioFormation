## 2026-02-25 - Static File Mount Exposing Config

**Vulnerability:** The entire project directory was mounted via `StaticFiles` to serve generated audio, which inadvertently exposed `00_CONFIG/engines.json` containing API keys.
**Learning:** `StaticFiles` in FastAPI serves all files in the directory by default. When mounting a directory that contains both public assets and private configuration, explicit blocking is required.
**Prevention:** Use a custom `StaticFiles` subclass that validates paths and blocks access to sensitive directories (like `00_CONFIG`) and hidden files.
