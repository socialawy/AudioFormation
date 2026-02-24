## 2024-05-24 - Static File Directory Traversal
**Vulnerability:** The `/projects` endpoint exposed the entire `PROJECTS_ROOT` directory via `StaticFiles`, allowing unauthorized access to sensitive configuration files like `00_CONFIG/engines.json` which contains API keys.
**Learning:** Using `StaticFiles` on a root directory that contains mixed content (public assets and private config) is dangerous. It relies on obscurity or external controls that might fail.
**Prevention:** Always use a custom `SafeStaticFiles` implementation (or similar middleware) to explicitly block sensitive directories, hidden files, and dangerous extensions when serving user-generated content directories. Better yet, serve only specific safe subdirectories if possible.
