
"""
API Routes for AudioFormation.

Handles project CRUD and status retrieval.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any

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

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    id: str


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


@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str):
    """Get project pipeline status."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        return load_pipeline_status(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
