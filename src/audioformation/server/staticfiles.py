
import os
from pathlib import Path
from typing import Set

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope


class SafeStaticFiles(StaticFiles):
    """
    Custom StaticFiles to block access to sensitive files/directories.

    Security Controls:
    1. Block hidden files (starting with .)
    2. Block sensitive directories (00_CONFIG)
    3. Block sensitive extensions (.env, .py, etc)
    """

    # Block access to these directories (relative to project root)
    # We assume the mount structure is /projects/{project_id}/{rest_of_path}
    # So the path passed to get_response is "{project_id}/{rest_of_path}"
    BLOCKED_DIRS: Set[str] = {"00_CONFIG", "__pycache__"}

    # Block files starting with dot
    BLOCK_HIDDEN: bool = True

    # Block specific extensions
    BLOCKED_EXTENSIONS: Set[str] = {
        ".py",
        ".pyc",
        ".env",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".lock",
        ".git",
    }

    async def get_response(self, path: str, scope: Scope):
        # path comes in as "ProjectName/folder/file.ext"

        # normalize path separator
        path_obj = Path(path)
        parts = path_obj.parts

        # 1. Block hidden files/directories
        if self.BLOCK_HIDDEN:
            for part in parts:
                if part.startswith("."):
                    raise HTTPException(status_code=404)

        # 2. Block sensitive directories
        # Expected structure: ProjectID / Directory / ...
        if len(parts) > 1:
            top_level_dir = parts[1]
            if top_level_dir in self.BLOCKED_DIRS:
                # Log security event?
                raise HTTPException(status_code=404)

        # 3. Block sensitive extensions
        _, ext = os.path.splitext(path)
        if ext.lower() in self.BLOCKED_EXTENSIONS:
            raise HTTPException(status_code=404)

        # Note: We don't block .json globally because manifest.json
        # in 07_EXPORT might be needed.
        # But engines.json is inside 00_CONFIG so it is blocked by directory check.

        return await super().get_response(path, scope)
