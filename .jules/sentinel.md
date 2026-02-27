
## 2024-03-01 - [FastAPI StaticFiles Config Exposure]
**Vulnerability:** The FastAPI application used `StaticFiles` to serve the `PROJECTS_ROOT` directory, which exposed sensitive configuration files like `00_CONFIG/engines.json` (containing API keys like `ELEVENLABS_API_KEY`) and hidden files to unauthenticated users.
**Learning:** Default static file servers in web frameworks do not inherently understand project-specific directory structures or sensitive paths. Using `StaticFiles` directly on a parent directory containing both public assets and private configs creates an immediate critical path traversal / information disclosure risk.
**Prevention:** Subclass `fastapi.staticfiles.StaticFiles` (or equivalent in other frameworks) to create a `SafeStaticFiles` handler that overrides the lookup logic (e.g., `lookup_path`) to explicitly block paths containing sensitive components (like `00_CONFIG` or hidden files). Always mount this safe handler instead of the default.
