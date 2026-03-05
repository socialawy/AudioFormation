## 2024-05-24 - [CRITICAL] FastAPI StaticFiles Exposes Sensitive Config
**Vulnerability:** Path traversal and sensitive file exposure via FastAPI `StaticFiles`.
**Learning:** Using `StaticFiles` out of the box to serve user directories or large application-managed directories can expose hidden files (`.env`, `.git`), configuration files, and script source code. In this project, `00_CONFIG/` might contain sensitive project data or `.py` source.
**Prevention:** Always subclass `StaticFiles` and override `get_response` to implement an explicit allow-list or strict deny-list for file types, hidden directories, and known sensitive paths (like `00_CONFIG` and `.py` files) before calling `super().get_response()`.
