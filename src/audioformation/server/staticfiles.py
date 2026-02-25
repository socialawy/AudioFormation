
from typing import Any
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

class SafeStaticFiles(StaticFiles):
    """
    Custom StaticFiles to block access to sensitive directories and files.
    """
    async def get_response(self, path: str, scope: Any):
        # Normalize path separators
        normalized_path = path.replace("\\", "/")
        parts = normalized_path.split("/")

        # Block specific sensitive directories
        # 00_CONFIG contains API keys (engines.json) and hardware info
        if "00_CONFIG" in parts:
             raise StarletteHTTPException(status_code=403, detail="Access denied to configuration files")

        # Block hidden files and directories (standard security practice)
        if any(part.startswith(".") for part in parts if part):
             raise StarletteHTTPException(status_code=403, detail="Access denied to hidden files")

        # Block source code and potentially sensitive extensions
        # .json is allowed because manifest.json and qc reports are needed by the frontend
        if path.lower().endswith(('.py', '.pyc', '.env')):
            raise StarletteHTTPException(status_code=403, detail="Access denied")

        return await super().get_response(path, scope)
