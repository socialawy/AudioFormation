"""
Safe static files handling to prevent directory traversal
and exposure of sensitive files.
"""

import os
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

class SafeStaticFiles(StaticFiles):
    """
    A custom StaticFiles handler that blocks access to sensitive directories
    and files within the projects root.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define forbidden patterns
        self.forbidden_dirs = {"00_config"}
        # Allow .json since it might be needed for frontend metadata, but block config files specifically
        self.forbidden_extensions = {".yml", ".yaml", ".env"}
        self.forbidden_files = {"engines.json", "hardware.json"}

    def lookup_path(self, path: str) -> tuple[str, "os.stat_result | None"]:
        # Block hidden files or directories
        parts = path.split("/")
        for part in parts:
            if part.startswith(".") and part != ".":
                raise HTTPException(status_code=403, detail="Forbidden")

            # Block sensitive directories (case-insensitive)
            if part.lower() in self.forbidden_dirs:
                raise HTTPException(status_code=403, detail="Forbidden")

        # Block sensitive file extensions
        _, ext = os.path.splitext(path)
        if ext.lower() in self.forbidden_extensions:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Block specific sensitive files (like engines.json and hardware.json)
        filename = os.path.basename(path).lower()
        if filename in self.forbidden_files:
            raise HTTPException(status_code=403, detail="Forbidden")

        return super().lookup_path(path)
