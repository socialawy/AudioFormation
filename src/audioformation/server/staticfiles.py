from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from starlette.responses import Response

class SafeStaticFiles(StaticFiles):
    """
    Secure static files serving that blocks access to sensitive directories
    and hidden files.
    """

    async def get_response(self, path: str, scope) -> Response:
        """Override to add security checks before serving files."""
        # 1. No hidden files or directories
        path_parts = path.split("/")
        if any(part.startswith(".") for part in path_parts if part):
            raise HTTPException(status_code=403, detail="Access denied")

        # 2. Prevent access to configuration and other sensitive directories
        if "00_CONFIG" in path_parts:
             raise HTTPException(status_code=403, detail="Access denied")

        # 3. Prevent access to python files or other sensitive extensions
        if path.endswith(".py") or (path.endswith(".json") and "00_CONFIG" in path):
             raise HTTPException(status_code=403, detail="Access denied")

        return await super().get_response(path, scope)
