import os
import typing
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

class SafeStaticFiles(StaticFiles):
    """
    Static file server that prevents access to sensitive project directories
    like 00_CONFIG and hidden files.
    """
    def lookup_path(
        self, path: str
    ) -> typing.Tuple[str, typing.Optional[os.stat_result]]:
        parts = path.split("/")

        # Block access to sensitive directories
        if "00_CONFIG" in parts:
            raise HTTPException(status_code=403, detail="Access to config directory is forbidden")

        # Block access to hidden files and directories
        if any(p.startswith(".") for p in parts if p):
            raise HTTPException(status_code=403, detail="Access to hidden files is forbidden")

        return super().lookup_path(path)
