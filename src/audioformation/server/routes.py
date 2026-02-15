
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
from audioformation.validation import validate_project
from audioformation.audio.processor import batch_process_project
from audioformation.audio.composer import generate_pad
from audioformation.export.mp3 import export_project_mp3
from audioformation.export.m4b import export_project_m4b
from audioformation.qc.final import scan_final_mix

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    id: str

class GenerateRequest(BaseModel):
    chapters: Optional[List[str]] = None
    engine: Optional[str] = None

class ComposeRequest(BaseModel):
    preset: str = "contemplative"
    duration: int = 60

class ExportRequest(BaseModel):
    format: str = "mp3"
    bitrate: int = 192


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


@router.post("/projects/{project_id}/validate")
async def trigger_validate(project_id: str):
    """Run validation gate (Node 2)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = validate_project(project_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/process")
async def trigger_process(project_id: str, background_tasks: BackgroundTasks):
    """Run audio processing/normalization (Node 4)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    background_tasks.add_task(batch_process_project, project_id)
    return {"message": "Processing started", "status": "running"}


@router.post("/projects/{project_id}/compose")
async def trigger_compose(
    project_id: str,
    request: ComposeRequest,
    background_tasks: BackgroundTasks,
):
    """Generate ambient background music (Node 5)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    from audioformation.project import get_project_path

    project_path = get_project_path(project_id)
    output_dir = project_path / "05_MUSIC" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"pad_{request.preset}.wav"

    background_tasks.add_task(
        generate_pad,
        request.preset,
        duration_sec=request.duration,
        output_path=output_path,
    )
    return {
        "message": f"Composing '{request.preset}' pad ({request.duration}s)",
        "status": "running",
    }


@router.post("/projects/{project_id}/export")
async def trigger_export(
    project_id: str,
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """Export project audio (Node 8)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    if request.format == "m4b":
        background_tasks.add_task(export_project_m4b, project_id)
    else:
        background_tasks.add_task(export_project_mp3, project_id)

    return {
        "message": f"Export started ({request.format})",
        "status": "running",
    }


@router.get("/projects/{project_id}/qc")
async def get_qc_reports(project_id: str):
    """Get QC scan and final mix reports."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    from audioformation.project import get_project_path
    import json

    project_path = get_project_path(project_id)
    reports = {}

    # Chunk QC reports
    gen_dir = project_path / "03_GENERATED"
    chunk_reports = list(gen_dir.glob("qc_report_*.json"))
    if chunk_reports:
        reports["chunk_qc"] = [
            json.loads(r.read_text(encoding="utf-8"))
            for r in sorted(chunk_reports)
        ]

    # Final mix QC report
    final_report = project_path / "06_MIX" / "qc_final_report.json"
    if final_report.exists():
        reports["final_qc"] = json.loads(
            final_report.read_text(encoding="utf-8")
        )

    if not reports:
        return {"message": "No QC reports found. Run qc or qc-final first."}

    return reports


@router.post("/projects/{project_id}/qc-final")
async def trigger_qc_final(project_id: str):
    """Run QC Final gate on mixed output (Node 7)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        report = scan_final_mix(project_id)
        return {
            "passed": report.passed,
            "total_files": report.total_files,
            "failed_files": report.failed_files,
            "results": [
                {
                    "filename": r.filename,
                    "status": r.status,
                    "lufs": r.lufs,
                    "true_peak": r.true_peak,
                    "messages": r.messages,
                }
                for r in report.results
            ],
        }
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
