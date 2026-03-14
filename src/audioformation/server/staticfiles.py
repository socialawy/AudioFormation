from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
from starlette.responses import Response
from starlette.types import Scope

class SafeStaticFiles(StaticFiles):
    """
    StaticFiles class that enforces security policies:
    - Blocks access to hidden files and directories (starting with '.')
    - Blocks access to 00_CONFIG directory
    - Blocks access to sensitive extensions (.json, .env, .sqlite, etc.)
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        parts = path.split('/')

        # Check for hidden files/directories
        if any(part.startswith('.') for part in parts if part):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check for sensitive directories
        if "00_CONFIG" in parts:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check for sensitive extensions
        if path.endswith(('.json', '.env', '.yaml', '.yml', '.sqlite', '.db')):
            raise HTTPException(status_code=403, detail="Access denied")

        return await super().get_response(path, scope)
