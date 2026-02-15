
"""
FastAPI application entry point.

Exposes the AudioFormation pipeline via REST API.
Port: 4001 (default).
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from audioformation import __version__
from audioformation.server.routes import router

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

# Mount static files (Dashboard)
# Must be mounted AFTER API routes to avoid capturing /api calls
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
