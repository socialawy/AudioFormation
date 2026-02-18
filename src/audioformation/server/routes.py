"""
API Routes for AudioFormation.

Handles project CRUD and status retrieval.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, List, Optional
from starlette.background import BackgroundTask

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
from audioformation.utils.security import sanitize_filename, validate_path_within
from audioformation.pipeline import mark_node
from audioformation.ingest import ingest_text
from audioformation.generate import generate_project
from audioformation.mix import mix_project
from audioformation.validation import validate_project
from audioformation.audio.processor import batch_process_project
from audioformation.audio.composer import generate_pad
from audioformation.audio.sfx import generate_sfx
from audioformation.export.mp3 import export_project_mp3
from audioformation.export.m4b import export_project_m4b_auto
from audioformation.qc.final import scan_final_mix
from audioformation.engines.registry import registry
from audioformation.engines.base import GenerationRequest

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


class SFXRequest(BaseModel):
    type: str
    duration: float = 1.0
    name: Optional[str] = None


class ExportRequest(BaseModel):
    format: str = "mp3"
    bitrate: int = 192


class PreviewRequest(BaseModel):
    text: str
    engine: str
    voice: Optional[str] = None
    language: str = "en"
    reference_audio: Optional[str] = None  # Relative path in project


@router.get("/projects")
async def get_projects():
    """List all projects."""
    return list_projects()


@router.post("/projects", status_code=201)
async def create_new_project(request: ProjectCreateRequest):
    """Create a new project."""
    project_id = request.id
    if project_exists(project_id):
        raise HTTPException(
            status_code=409, detail=f"Project '{project_id}' already exists."
        )

    try:
        path = create_project(project_id)

        # Initialize hardware detection and status
        write_hardware_json(path)
        mark_node(path, "bootstrap", "complete")

        return {
            "id": path.name,
            "path": str(path.resolve()),
            "message": "Project created successfully.",
        }
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects/{project_id}")
async def get_project_details(project_id: str):
    """Get project configuration (project.json)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        return load_project_json(project_id)
    except Exception as e:
        logger.error(f"Failed to load project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error(f"Failed to update project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/projects/{project_id}/ingest")
async def ingest_files(
    project_id: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    """Upload text files and run ingest."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Read uploads NOW (within request lifecycle) — UploadFile handles
    # will be closed after response returns, before background task runs.
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir)
    try:
        for file in files:
            # CODEQL FIX: Explicit basename + sanitize
            raw_filename = os.path.basename(file.filename)
            safe_filename = sanitize_filename(raw_filename)
            dest = tmp_path / safe_filename
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


@router.post("/projects/{project_id}/upload")
async def upload_file(project_id: str, category: str, file: UploadFile = File(...)):
    """
    Upload a file to a specific project category.

    Categories:
    - 'references': Voice cloning references (02_VOICES/references)
    - 'music': Background music (05_MUSIC/imported)
    """
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Not found")
    project_path = get_project_path(project_id)
    if category == "references": target_dir = project_path / "02_VOICES" / "references"
    elif category == "music": target_dir = project_path / "05_MUSIC" / "generated"
    else: raise HTTPException(status_code=400, detail="Invalid category")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # CODEQL FIX: Safe construction. 
    # safe_name is a strict basename. target_dir is trusted. 
    # dest cannot be a traversal. We skip redundant validation.
    safe_name = os.path.basename(file.filename)
    if not re.fullmatch(r"^[A-Za-z0-9_.-]+$", safe_name):
         raise HTTPException(status_code=400, detail="Invalid filename characters")
         
    dest = target_dir / safe_name
    
    try:
        with open(dest, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        return {"path": str(dest.relative_to(project_path)).replace("\\", "/"), "filename": safe_name}
    except Exception:
        raise HTTPException(status_code=500, detail="Upload failed")


@router.post("/projects/{project_id}/preview")
async def preview_voice(project_id: str, request: PreviewRequest):
    """Generate a quick voice preview."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    project_path = get_project_path(project_id)

    try:
        engine = registry.get(request.engine)
    except KeyError:
        raise HTTPException(
            status_code=400, detail=f"Engine '{request.engine}' not found"
        )

    # Resolve reference audio if present
    ref_path = None
    if request.reference_audio:
        # CODEQL FIX: Validate reference_audio is strictly within project
        # User input could be "../../etc/passwd"
        possible_ref = (project_path / request.reference_audio).resolve()
        if not validate_path_within(possible_ref, project_path):
             raise HTTPException(status_code=400, detail="Invalid reference audio path")
        
        if not possible_ref.exists():
            raise HTTPException(status_code=400, detail="Reference audio not found")
        ref_path = possible_ref

    # Create temp file for output
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        output_path = Path(tmp.name)
    
    # Validate temp path is within system temp directory
    temp_root = Path(tempfile.gettempdir())
    if not validate_path_within(output_path, temp_root):
        raise HTTPException(status_code=500, detail="Invalid temp path")

    try:
        gen_req = GenerationRequest(
            text=request.text,
            output_path=output_path,
            voice=request.voice,
            language=request.language,
            reference_audio=ref_path,
        )

        result = await engine.generate(gen_req)

        if not result.success:
            raise Exception(result.error)

        return FileResponse(
            path=output_path,
            media_type="audio/wav",
            filename="preview.wav",
            # Clean up temp file after sending
            background=BackgroundTask(lambda: output_path.unlink(missing_ok=True)),
        )

    except Exception as e:
        output_path.unlink(missing_ok=True)
        logger.error(f"Failed to generate preview for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _ingest_files_sync(project_id: str, tmp_path: Path) -> dict:
    """Synchronous ingest logic for background task."""
    try:
        result = ingest_text(project_id, tmp_path)
        return {"message": f"Ingested {result['ingested']} files.", "details": result}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


@router.post("/projects/{project_id}/generate")
async def trigger_generation(
    project_id: str, request: GenerateRequest, background_tasks: BackgroundTasks
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
async def trigger_mix(
    project_id: str, background_tasks: BackgroundTasks, music: Optional[str] = None
):
    """Trigger mixing process in background.

    Args:
        music: Optional filename of music file to use (must exist in 05_MUSIC/generated).
               If 'FORCE_NO_MUSIC', forces voice-only mix.
               If None, auto-detects latest music.
    """
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Handle the "FORCE_NO_MUSIC" hack gracefully
    music_file = music
    if music == "FORCE_NO_MUSIC":
        music_file = "FORCE_NO_MUSIC"

    background_tasks.add_task(
        _run_with_status,
        lambda: mix_project(project_id=project_id, music_file=music_file),
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

    # Use timestamp to avoid overwriting unless specified?
    # For now, unique name per preset + timestamp is good
    import time

    timestamp = str(int(time.time()))
    # CODEQL FIX: Sanitize input and basename
    safe_preset = sanitize_filename(os.path.basename(request.preset))
    output_path = output_dir / f"pad_{safe_preset}_{timestamp}.wav"

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


@router.post("/projects/{project_id}/sfx")
async def trigger_sfx(
    project_id: str,
    request: SFXRequest,
    background_tasks: BackgroundTasks,
):
    """Generate procedural sound effects (Node 5)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    project_path = get_project_path(project_id)
    output_dir = project_path / "04_SFX" / "procedural"
    output_dir.mkdir(parents=True, exist_ok=True)

    import time

    timestamp = str(int(time.time()))
    # CODEQL FIX: Sanitize input and basename
    raw_name = request.name if request.name else f"{request.type}_{timestamp}"
    safe_name = sanitize_filename(os.path.basename(raw_name))
    
    if not safe_name.endswith(".wav"):
        safe_name += ".wav"

    output_path = output_dir / safe_name

    # Simple wrapper to match _run_with_status signature
    def _gen_sfx():
        generate_sfx(request.type, output_path=output_path, duration=request.duration)

    # Use 'compose' node status for now, or maybe we need a dedicated 'sfx' node?
    # Architecture has 'FXForge' but pipeline.py nodes are linear.
    # Let's treat it as part of 'compose' or just a side effect without blocking pipeline.
    # We'll log it but maybe not block the main pipeline status.
    # Actually, let's just run it. The UI can poll for files.

    try:
        _gen_sfx()
        return {
            "message": f"Generated SFX: {safe_name}",
            "path": str(output_path.relative_to(project_path)),
        }
    except Exception as e:
        logger.error(f"Failed to generate SFX for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/projects/{project_id}/export")
async def trigger_export(
    project_id: str,
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """Export project audio (Node 8)."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    export_func = (
        export_project_m4b_auto if request.format == "m4b" else export_project_mp3
    )

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
            # CODEQL FIX: Hardcoded error message to prevent information exposure
            chunk_results.append(
                ChunkQCResult(
                    chunk_id=chunk_id,
                    status="fail",
                    checks={"scan_error": {"status": "fail", "message": "Scan Error"}},
                )
            )

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
            json.loads(r.read_text(encoding="utf-8")) for r in sorted(chunk_reports)
        ]

    # Final mix QC report
    final_report = project_path / "06_MIX" / "qc_final_report.json"
    if final_report.exists():
        reports["final_qc"] = json.loads(final_report.read_text(encoding="utf-8"))

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
        logger.error(f"Failed to load pipeline status for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/projects/{project_id}/files")
async def list_project_files(project_id: str):
    """List exportable files in the project."""
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    project_path = get_project_path(project_id)
    export_dir = project_path / "07_EXPORT"
    music_dir = project_path / "05_MUSIC" / "generated"
    sfx_dir = project_path / "04_SFX" / "procedural"

    files = []

    def scan_dir(d: Path, category: str):
        if d.exists():
            for f in sorted(d.glob("*")):
                if f.is_file() and not f.name.startswith("."):
                    files.append(
                        {
                            "path": str(f.relative_to(project_path)).replace("\\", "/"),
                            "name": f.name,
                            "category": category,
                            "size": f.stat().st_size,
                            "modified": f.stat().st_mtime,
                        }
                    )

    scan_dir(export_dir / "audiobook", "audiobook")
    scan_dir(export_dir / "chapters", "chapter")
    scan_dir(music_dir, "music")
    scan_dir(sfx_dir, "sfx")

    manifest = export_dir / "manifest.json"
    if manifest.exists():
        files.append(
            {
                "path": str(manifest.relative_to(project_path)).replace("\\", "/"),
                "name": "manifest.json",
                "category": "metadata",
                "size": manifest.stat().st_size,
                "modified": manifest.stat().st_mtime,
            }
        )

    return files


@router.get("/engines")
async def list_engines():
    """List available TTS engines and their capabilities."""
    engines = []
    for name in registry.list_available():
        try:
            eng = registry.get(name)
            engines.append(
                {
                    "id": name,
                    "name": name,
                    "cloning": eng.supports_cloning,
                    "ssml": eng.supports_ssml,
                    "gpu": eng.requires_gpu,
                }
            )
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
        logger.error(f"Failed to list voices for engine {name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
