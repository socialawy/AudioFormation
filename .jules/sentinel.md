## 2024-05-28 - Fast API Security Handling Enhancement
**Vulnerability:** Fast API routes might expose sensitive information if exception handling doesn't use `raise HTTPException` with minimal explicit messages.
**Learning:** Returning error messages should abstract internal errors while retaining useful logs locally via `logger.error()`.
**Prevention:** Always use `HTTPException` appropriately configured to mask generic or traceback information from users.

## 2024-05-28 - SafeStaticFiles Path Normalization Crash
**Vulnerability:** `SafeStaticFiles` implemented in FastAPI attempted to call `.lower()` directly on a `Path` object which raises an `AttributeError`. A malicious user might craft requests specifically to trigger unhandled internal server crashes, or bypass security rules by supplying NoneType or unexpected objects that crash the normalizer before the actual path block checks occur (failing open if error handlers are improperly set).
**Learning:** When writing path normalization for blocking secure files, ensure proper type coercion. A crash in security checks creates blind spots and potential DoS.
**Prevention:** Explicitly cast external inputs to `str` before calling string normalization methods, ensuring robust error-free evaluation: `Path(str(path).lower())`.
