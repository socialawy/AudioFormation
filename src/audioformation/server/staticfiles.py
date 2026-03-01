import os
import logging
from typing import Tuple, Union
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("audioformation.api")

class SafeStaticFiles(StaticFiles):
    """
    Custom StaticFiles wrapper that prevents serving sensitive files/directories.

    Blocks access to:
    - 00_CONFIG directory
    - Hidden files (starting with .)
    - project.json
    """

    def lookup_path(self, path: str) -> Tuple[str, Union[os.stat_result, None]]:
        # Block hidden files and directories
        parts = path.split("/")
        if any(p.startswith(".") for p in parts if p):
            logger.warning(f"Blocked access to hidden file/directory: {path}")
            return "", None

        # Block 00_CONFIG directory
        if "00_CONFIG" in parts:
            logger.warning(f"Blocked access to sensitive directory 00_CONFIG: {path}")
            return "", None

        # Block project.json
        if "project.json" in parts:
            logger.warning(f"Blocked access to project.json: {path}")
            return "", None

        # Delegate to the original lookup
        full_path, stat_result = super().lookup_path(path)

        return full_path, stat_result
