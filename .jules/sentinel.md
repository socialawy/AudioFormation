## 2025-02-24 - Exception Handling in SafeStaticFiles
**Vulnerability:** SafeStaticFiles incorrectly normalizes `path` to lowercase using `p = Path(path).lower()`, but `Path` objects don't have a `.lower()` method. This throws an `AttributeError` instead of handling the security check and raises an unhandled internal error.
**Learning:** Security controls can bypass themselves if they contain runtime bugs that cause unhandled exceptions ("fail open" or unpredictable error responses). String operations must be done before path instantiation, e.g. `Path(str(path).lower())`.
**Prevention:** Always validate that security logic functions fail cleanly or correctly and handle edge-cases and None-type values properly to avoid breaking applications.
