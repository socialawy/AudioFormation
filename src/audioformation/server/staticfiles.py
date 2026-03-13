"""
Secure static file serving for AudioFormation.
Blocks access to sensitive files and directories within the projects folder.
"""

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response


class SafeStaticFiles(StaticFiles):
    """
    StaticFiles subclass that blocks access to sensitive paths.

    Blocked:
    - Paths containing '00_CONFIG' (secrets, API keys)
    - Hidden files/directories (starting with '.')
    - Sensitive extensions: .json, .yaml, .toml, .py, .env
      (Exception: manifest.json is allowed for export metadata)
    """

    async def get_response(self, path: str, scope):
        # path is relative to the mount point, e.g., "MY_NOVEL/00_CONFIG/engines.json"

        segments = path.split("/")

        # 1. Block sensitive directories
        if "00_CONFIG" in segments:
            return Response("Access Forbidden: Sensitive Directory", status_code=403)

        # 2. Block hidden files/directories
        if any(seg.startswith(".") for seg in segments):
            return Response("Access Forbidden: Hidden File", status_code=403)

        # 3. Block sensitive file extensions
        lower_path = path.lower()
        if lower_path.endswith("manifest.json"):
            # Explicitly allowed
            pass
        elif (
            lower_path.endswith(".json")
            or lower_path.endswith(".yaml")
            or lower_path.endswith(".yml")
            or lower_path.endswith(".toml")
            or lower_path.endswith(".py")
            or lower_path.endswith(".env")
        ):
            return Response("Access Forbidden: Sensitive File Type", status_code=403)

        return await super().get_response(path, scope)
