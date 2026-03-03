## 2024-03-04 - [StaticFiles Data Exposure]
**Vulnerability:** The `/projects` directory was mounted using standard FastAPI `StaticFiles`, which would allow any user to download arbitrary files within the project directories, including sensitive configuration like `00_CONFIG/hardware.json` and potential API keys in `.env` or project data.
**Learning:** Even though path traversal beyond the mount point is prevented, exposing an entire working directory can still leak internal configuration files if they are not explicitly filtered.
**Prevention:** Subclass `StaticFiles` into a `SafeStaticFiles` class that explicitly blocks access to hidden files (`.`), sensitive directories (`00_CONFIG`), and configuration extensions (`.env`, `.json`, etc.) before serving the file.
