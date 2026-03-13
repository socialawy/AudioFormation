import os
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from starlette.responses import Response


class SafeStaticFiles(StaticFiles):
    """
    A more secure implementation of StaticFiles that prevents access to
    sensitive files and directories within the served directory.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Directories that should never be served directly
        self.blocked_dirs = {"00_CONFIG", ".git", ".env"}

        # File extensions that should never be served directly
        self.blocked_extensions = {".env", ".key", ".pem", ".log"}

    async def get_response(self, path: str, scope) -> Response:
        # Check if the path contains any blocked directories
        path_parts = path.split("/")
        for part in path_parts:
            if part in self.blocked_dirs or part.startswith("."):
                raise HTTPException(status_code=403, detail="Access denied")

        # Check file extension
        ext = os.path.splitext(path)[1].lower()
        if ext in self.blocked_extensions:
            raise HTTPException(status_code=403, detail="Access denied")

        return await super().get_response(path, scope)
