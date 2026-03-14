## 2025-03-01 - Missing SafeStaticFiles implementation
**Vulnerability:** FastApi StaticFiles serves everything in the directory, meaning sensitive data (e.g. project configuration) can be exposed.
**Learning:** Static files exposing sensitive data
**Prevention:** Use a custom SafeStaticFiles wrapper.
