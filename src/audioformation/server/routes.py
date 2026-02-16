
"""
API Routes for AudioFormation.

Handles project CRUD and status retrieval.
"""

import asyncio
import json
import logging
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
    get_project_path,
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
from audioformation.export.m4b import export_project_m4b_auto
from audioformation.qc.final import scan_final_mix
from audioformation.engines.registry import registry

router = APIRouter()
logger = logging.getLogger("audioformation.api")


async def _run_with_status(func, project_id: str, node: str):
    """Wrapper that marks node running/complete/failed around any pipeline function.
    
    Handles both sync and async functions by checking if the result is a coroutine.
    """
    path = get_project_path(project_id)
    try:
        mark_node(path, node, "running")
        result = func()  # Call lambda/closure
        # If func() returned a coroutine (async function), await it
        if asyncio.iscoroutine(result):
            await result
        mark_node(path, node, "complete")
    except Exception as e:
        logger.exception(f"Background task '{node}' failed for {project_id}: {e}")
        mark_node(path, node, "failed", error=str(e))


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
async def ingest_files(project_id: str, background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Upload text files and run ingest."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Read uploads NOW (within request lifecycle) — UploadFile handles
    # will be closed after response returns, before background task runs.
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir)
    try:
        for file in files:
            dest = tmp_path / file.filename
            with open(dest, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    background_tasks.add_task(
        _run_with_status,
        lambda: _ingest_files_sync(project_id, tmp_path),
        project_id,
        "ingest",
    )

    return {"message": "Ingest started", "status": "running"}


def _ingest_files_sync(project_id: str, tmp_path: Path) -> dict:
    """Synchronous ingest logic for background task."""
    try:
        result = ingest_text(project_id, tmp_path)
        return {
            "message": f"Ingested {result['ingested']} files.",
            "details": result
        }
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


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
        _run_with_status,
        lambda: generate_project(
            project_id=project_id,
            engine_name=request.engine,
            chapters=request.chapters,
        ),
        project_id,
        "generate",
    )
    
    return {"message": "Generation started", "status": "running"}


@router.post("/projects/{project_id}/mix")
async def trigger_mix(project_id: str, background_tasks: BackgroundTasks):
    """Trigger mixing process in background."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    background_tasks.add_task(
        _run_with_status,
        lambda: mix_project(project_id=project_id),
        project_id,
        "mix",
    )
    
    return {"message": "Mixing started", "status": "running"}


@router.post("/projects/{project_id}/validate")
async def trigger_validate(project_id: str, background_tasks: BackgroundTasks):
    """Run validation gate (Node 2)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    background_tasks.add_task(
        _run_with_status,
        lambda: validate_project(project_id),
        project_id,
        "validate",
    )
    
    return {"message": "Validation started", "status": "running"}


@router.post("/projects/{project_id}/process")
async def trigger_process(project_id: str, background_tasks: BackgroundTasks):
    """Run audio processing/normalization (Node 4)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    background_tasks.add_task(
        _run_with_status,
        lambda: batch_process_project(project_id),
        project_id,
        "process",
    )
    
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

    project_path = get_project_path(project_id)
    output_dir = project_path / "05_MUSIC" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"pad_{request.preset}.wav"


    background_tasks.add_task(
        _run_with_status,
        lambda: generate_pad(
            request.preset,
            duration_sec=request.duration,
            output_path=output_path,
        ),
        project_id,
        "compose",
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

    export_func = export_project_m4b_auto if request.format == "m4b" else export_project_mp3

    background_tasks.add_task(
        _run_with_status,
        lambda: export_func(project_id, bitrate=request.bitrate),
        project_id,
        "export",
    )

    return {
        "message": f"Export started ({request.format})",
        "status": "running",
    }


@router.post("/projects/{project_id}/qc-scan")
async def trigger_qc_scan(project_id: str, background_tasks: BackgroundTasks):
    """Run QC scan on generated audio (Node 3.5)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    background_tasks.add_task(
        _run_with_status,
        lambda: _qc_scan_sync(project_id),
        project_id,
        "qc_scan",
    )
    
    return {"message": "QC scan started", "status": "running"}


def _qc_scan_sync(project_id: str) -> dict:
    """Synchronous QC scan logic for background task."""
    from audioformation.qc.scanner import scan_chunk, QCReport, ChunkQCResult
    from audioformation.qc.report import save_report

    project_path = get_project_path(project_id)
    project_data = load_project_json(project_id)
    qc_config = project_data.get("qc", {})

    raw_dir = project_path / "03_GENERATED" / "raw"

    if not raw_dir.exists():
        raise FileNotFoundError(f"Generated audio directory not found: {raw_dir}")

    audio_files = sorted(raw_dir.glob("*.wav")) + sorted(raw_dir.glob("*.mp3"))

    if not audio_files:
        return {"message": "No audio files found to scan", "scanned": 0}

    target_lufs = project_data.get("mix", {}).get("target_lufs", -16.0)
    chunk_results: list[ChunkQCResult] = []

    for audio_file in audio_files:
        chunk_id = audio_file.stem
        try:
            result = scan_chunk(
                audio_path=audio_file,
                chunk_id=chunk_id,
                config=qc_config,
                target_lufs=target_lufs,
            )
            chunk_results.append(result)
        except Exception as e:
            # Create a failed ChunkQCResult for files that error
            chunk_results.append(ChunkQCResult(
                chunk_id=chunk_id,
                status="fail",
                checks={"scan_error": {"status": "fail", "message": str(e)}},
            ))

    report = QCReport(
        project_id=project_id,
        chapter_id=None,
        chunks=chunk_results,
    )

    gen_dir = project_path / "03_GENERATED"
    report_path = save_report(report, gen_dir)

    return {
        "message": "QC scan completed",
        "scanned": len(chunk_results),
        "passed": report.pass_count,
        "warned": report.warn_count,
        "failed": report.fail_count,
        "fail_rate": report.fail_rate,
        "report_path": str(report_path.relative_to(project_path)),
    }


@router.get("/projects/{project_id}/qc")
async def get_qc_reports(project_id: str):
    """Get QC scan and final mix reports."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

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
async def trigger_qc_final(project_id: str, background_tasks: BackgroundTasks):
    """Run QC Final gate on mixed output (Node 7)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    background_tasks.add_task(
        _run_with_status,
        lambda: _qc_final_sync(project_id),
        project_id,
        "qc_final",
    )
    
    return {"message": "QC Final started", "status": "running"}


def _qc_final_sync(project_id: str) -> dict:
    """Synchronous QC final logic for background task."""
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


@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str):
    """Get project pipeline status."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        return load_pipeline_status(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── New Endpoints for Dashboard v2 ───────────────────────────

@router.get("/engines")
async def list_engines():
    """List available TTS engines and their capabilities."""
    engines = []
    for name in registry.list_available():
        try:
            eng = registry.get(name)
            engines.append({
                "id": name,
                "name": name,
                "cloning": eng.supports_cloning,
                "ssml": eng.supports_ssml,
                "gpu": eng.requires_gpu
            })
        except Exception as e:
            logger.warning(f"Failed to load engine {name}: {e}")
            engines.append({"id": name, "error": str(e)})
    return engines


@router.get("/engines/{name}/voices")
async def list_engine_voices(name: str, lang: Optional[str] = None):
    """List voices for a specific engine, optionally filtered by language."""
    try:
        engine = registry.get(name)
        voices = await engine.list_voices(language=lang)
        return voices
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Engine '{name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/hardware")
async def get_project_hardware(project_id: str):
    """Get project hardware detection info (hardware.json)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    
    path = get_project_path(project_id) / "00_CONFIG" / "hardware.json"
    if not path.exists():
        return {}
    
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get("/projects/{project_id}/files")
async def list_project_files(project_id: str):
    """List exportable files in the project."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
        
    project_path = get_project_path(project_id)
    export_dir = project_path / "07_EXPORT"
    
    files = []
    
    def scan_dir(d: Path, category: str):
        if d.exists():
            for f in sorted(d.glob("*")):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "path": str(f.relative_to(project_path)).replace("\\", "/"),
                        "name": f.name,
                        "category": category,
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime
                    })

    scan_dir(export_dir / "audiobook", "audiobook")
    scan_dir(export_dir / "chapters", "chapter")
    
    manifest = export_dir / "manifest.json"
    if manifest.exists():
        files.append({
            "path": str(manifest.relative_to(project_path)).replace("\\", "/"),
            "name": "manifest.json",
            "category": "metadata",
            "size": manifest.stat().st_size,
            "modified": manifest.stat().st_mtime
        })
        
    return files
