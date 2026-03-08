"""Entry point for `python -m audioformation`."""

import sys

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for CLI symbols)
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

from audioformation.cli import main

if __name__ == "__main__":
    main()
