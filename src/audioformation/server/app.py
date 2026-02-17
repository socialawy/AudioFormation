"""
FastAPI application entry point.

Exposes the AudioFormation pipeline via REST API.
Port: 4001 (default).
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

from audioformation import __version__
from audioformation.server.routes import router
from audioformation.config import PROJECTS_ROOT

app = FastAPI(
    title="AudioFormation API",
    version=__version__,
    description="Production audio pipeline API",
)

# Enable CORS for local dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local dev; restrict in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


# Mount projects directory for audio streaming (e.g., /projects/MY_NOVEL/...)
# Ensure directory exists so mount doesn't fail or get skipped
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/projects", StaticFiles(directory=PROJECTS_ROOT), name="projects")

# Mount static files (Dashboard)
# Must be mounted AFTER API routes to avoid capturing /api calls
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
