
"""
API Routes for AudioFormation.

Handles project CRUD and status retrieval.
"""

import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Any, List, Optional

from audioformation.project import (
    list_projects,
    create_project,
    load_project_json,
    save_project_json,
    load_pipeline_status,
    project_exists,
)
from audioformation.utils.hardware import write_hardware_json
from audioformation.pipeline import mark_node
from audioformation.ingest import ingest_text
from audioformation.generate import generate_project
from audioformation.mix import mix_project

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    id: str

class GenerateRequest(BaseModel):
    chapters: Optional[List[str]] = None
    engine: Optional[str] = None


@router.get("/projects")
async def get_projects():
    """List all projects."""
    return list_projects()


@router.post("/projects", status_code=201)
async def create_new_project(request: ProjectCreateRequest):
    """Create a new project."""
    project_id = request.id
    if project_exists(project_id):
        raise HTTPException(status_code=409, detail=f"Project '{project_id}' already exists.")

    try:
        path = create_project(project_id)
        
        # Initialize hardware detection and status
        write_hardware_json(path)
        mark_node(path, "bootstrap", "complete")
        
        return {
            "id": path.name,
            "path": str(path.resolve()),
            "message": "Project created successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project_details(project_id: str):
    """Get project configuration (project.json)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        return load_project_json(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}")
async def update_project(project_id: str, project_data: dict[str, Any]):
    """Update project configuration (project.json)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Safety check: ensure ID in body matches URL if present
    if project_data.get("id") and project_data["id"] != project_id:
         raise HTTPException(status_code=400, detail="Project ID mismatch")
         
    try:
        save_project_json(project_id, project_data)
        return {"message": "Project updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/ingest")
async def ingest_files(project_id: str, files: List[UploadFile] = File(...)):
    """Upload text files and run ingest."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Create a temporary directory to receive uploads
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            for file in files:
                dest = tmp_path / file.filename
                with open(dest, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            
            # Run ingest logic
            result = ingest_text(project_id, tmp_path)
            
            return {
                "message": f"Ingested {result['ingested']} files.",
                "details": result
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


@router.post("/projects/{project_id}/generate")
async def trigger_generation(
    project_id: str, 
    request: GenerateRequest, 
    background_tasks: BackgroundTasks
):
    """Trigger TTS generation in the background."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    background_tasks.add_task(
        generate_project, 
        project_id=project_id, 
        engine_name=request.engine, 
        chapters=request.chapters
    )
    
    return {"message": "Generation started", "status": "running"}


@router.post("/projects/{project_id}/mix")
async def trigger_mix(project_id: str, background_tasks: BackgroundTasks):
    """Trigger mixing process in background."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    # For now, auto-detect music file inside mix_project
    background_tasks.add_task(mix_project, project_id=project_id)
    
    return {"message": "Mixing started", "status": "running"}


@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str):
    """Get project pipeline status."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        return load_pipeline_status(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
