
"""
AudioFormation CLI — Click command groups.

Phase 1 commands: new, list, status, hardware, validate, ingest,
generate, qc, export, quick, engines, run.

Phase 2 commands: cast (manage characters), compose (ambient music),
                  preview (fast check), compare (A/B testing).

Phase 3 commands: mix, qc-final, serve (API).
                  sfx (FXForge).
"""

import asyncio
import json
import sys
import shutil
import time
from pathlib import Path

import click

from audioformation import __version__
from audioformation.config import PIPELINE_NODES, HARD_GATES, AUTO_GATES, API_PORT
from audioformation.pipeline import mark_node


# ──────────────────────────────────────────────
# Async helper
# ──────────────────────────────────────────────


def _run_async(coro):
    """Run an async coroutine from synchronous Click context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# ──────────────────────────────────────────────
# Main group
# ──────────────────────────────────────────────


@click.group()
@click.version_option(__version__, prog_name="audioformation")
def main() -> None:
    """🏭 AudioFormation — Production audio pipeline."""
    pass


# ──────────────────────────────────────────────
# Project management
# ──────────────────────────────────────────────


@main.command()
@click.argument("name")
def new(name: str) -> None:
    """Create a new audio project."""
    from audioformation.project import create_project
    from audioformation.utils.hardware import write_hardware_json

    try:
        project_path = create_project(name)
    except (FileExistsError, ValueError) as e:
        click.secho(f"✗ {e}", fg="red")
        sys.exit(1)

    click.echo("  Detecting hardware...")
    hw = write_hardware_json(project_path)

    click.secho(f"✓ Created project: {project_path.name}", fg="green")
    click.echo(f"  Path: {project_path.resolve()}")

    # Write pipeline status — bootstrap complete
    mark_node(project_path, "bootstrap", "complete")

    if hw.get("gpu_available"):
        click.echo(f"  GPU:  {hw['gpu_name']} ({hw['vram_total_gb']} GB VRAM)")
        click.echo(f"  VRAM strategy: {hw['recommended_vram_strategy']}")
    else:
        click.echo("  GPU:  None detected (CPU mode)")

    if hw.get("ffmpeg_available"):
        click.echo("  ffmpeg: ✓")
    else:
        click.secho("  ffmpeg: ✗ NOT FOUND — install ffmpeg and add to PATH", fg="yellow")

    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Add text files to {project_path.name}/01_TEXT/chapters/")
    click.echo(f"  2. Edit {project_path.name}/project.json (chapters + characters)")
    click.echo(f"  3. Run: audioformation validate {project_path.name}")


@main.command("list")
def list_projects() -> None:
    """List all projects."""
    from audioformation.project import list_projects as _list

    projects = _list()

    if not projects:
        click.echo("No projects found.")
        click.echo("  Create one: audioformation new MY_PROJECT")
        return

    click.echo(f"{'ID':<30} {'Created':<22} {'Chapters':<10} {'Stage':<15} {'Languages'}")
    click.echo("─" * 95)

    for p in projects:
        langs = ", ".join(p.get("languages", []))
        click.echo(
            f"{p['id']:<30} "
            f"{p['created'][:19]:<22} "
            f"{p['chapters']:<10} "
            f"{p['pipeline_node']:<15} "
            f"{langs}"
        )


@main.command()
@click.argument("project_id")
def status(project_id: str) -> None:
    """Show detailed project status."""
    from audioformation.project import load_project_json, load_pipeline_status

    if not _project_guard(project_id):
        return

    try:
        pj = load_project_json(project_id)
        ps = load_pipeline_status(project_id)
    except FileNotFoundError as e:
        click.secho(f"✗ {e}", fg="red")
        sys.exit(1)

    click.secho(f"Project: {pj['id']}", fg="cyan", bold=True)
    click.echo(f"  Created:    {pj.get('created', 'unknown')}")
    click.echo(f"  Languages:  {', '.join(pj.get('languages', []))}")
    click.echo(f"  Chapters:   {len(pj.get('chapters', []))}")
    click.echo(f"  Characters: {', '.join(pj.get('characters', {}).keys())}")
    click.echo()

    click.secho("Pipeline Status:", bold=True)
    nodes = ps.get("nodes", {})

    for node in PIPELINE_NODES:
        node_data = nodes.get(node, {})
        node_status = node_data.get("status", "pending")

        if node_status == "complete":
            icon = click.style("✓", fg="green")
        elif node_status == "partial":
            icon = click.style("◐", fg="yellow")
        elif node_status == "running":
            icon = click.style("▶", fg="blue")
        elif node_status == "failed":
            icon = click.style("✗", fg="red")
        elif node_status == "skipped":
            icon = click.style("⊘", fg="white")
        else:
            icon = click.style("·", fg="white")

        gate = ""
        if node in HARD_GATES:
            gate = " [HARD GATE]"
        elif node in AUTO_GATES:
            gate = " [AUTO GATE]"

        click.echo(f"  {icon} {node:<15} {node_status:<12}{gate}")

        # Chapter-level detail for generate node
        if node == "generate" and "chapters" in node_data:
            chapters = node_data["chapters"]
            done = sum(1 for c in chapters.values() if c.get("status") == "complete")
            total = len(chapters)
            click.echo(f"    Chapters: {done}/{total} complete")


@main.command()
def hardware() -> None:
    """Detect and display hardware capabilities."""
    from audioformation.utils.hardware import detect_all

    hw = detect_all()

    click.secho("Hardware Detection:", bold=True)
    click.echo()

    if hw.get("gpu_available"):
        click.secho("  GPU:", fg="green")
        click.echo(f"    Name:     {hw['gpu_name']}")
        click.echo(f"    VRAM:     {hw['vram_total_gb']} GB total, {hw['vram_free_gb']} GB free")
        click.echo(f"    CUDA:     {hw.get('cuda_version', 'unknown')}")
        click.echo(f"    Strategy: {hw['recommended_vram_strategy']}")
    else:
        click.secho("  GPU: None detected", fg="yellow")
        click.echo("    XTTS will use CPU (slower) or fall back to edge-tts")

    click.echo()

    if hw.get("ffmpeg_available"):
        click.secho("  ffmpeg: ✓", fg="green")
        click.echo(f"    Path:    {hw['ffmpeg_path']}")
        click.echo(f"    Version: {hw.get('ffmpeg_version', 'unknown')}")
    else:
        click.secho("  ffmpeg: ✗ NOT FOUND", fg="red")
        click.echo("    Install: https://ffmpeg.org/download.html")
        click.echo("    Required for audio processing and export.")


# ──────────────────────────────────────────────
# Character Management (Cast)
# ──────────────────────────────────────────────


@main.group()
def cast() -> None:
    """Manage project characters and voices."""
    pass


@cast.command("list")
@click.argument("project_id")
def cast_list(project_id: str) -> None:
    """List characters in a project."""
    from audioformation.project import load_project_json

    if not _project_guard(project_id):
        return

    try:
        pj = load_project_json(project_id)
    except FileNotFoundError:
        click.secho("✗ project.json not found.", fg="red")
        sys.exit(1)

    characters = pj.get("characters", {})
    if not characters:
        click.echo(f"No characters found in project {project_id}.")
        return

    click.secho(f"Cast for {project_id}:", bold=True)
    click.echo(f"{'ID':<15} {'Name':<20} {'Engine':<12} {'Voice/Ref'}")
    click.echo("─" * 80)

    for char_id, char_data in characters.items():
        name = char_data.get("name", "")
        engine = char_data.get("engine", "")
        voice = char_data.get("voice") or char_data.get("reference_audio") or ""
        
        # Truncate long paths for display
        if len(voice) > 30 and "/" in voice:
            voice = "..." + voice[-27:]

        click.echo(f"{char_id:<15} {name[:19]:<20} {engine:<12} {voice}")


@cast.command("add")
@click.argument("project_id")
@click.option("--id", "char_id", required=True, help="Character ID (e.g., 'hero').")
@click.option("--name", required=True, help="Display name.")
@click.option("--engine", default="edge", help="TTS engine (default: edge).")
@click.option("--voice", default=None, help="Voice ID (for edge/cloud) or None.")
@click.option("--dialect", default="msa", help="Dialect code (msa, eg, etc.).")
@click.option("--persona", default="", help="Description of character persona.")
def cast_add(project_id: str, char_id: str, name: str, engine: str, voice: str | None, dialect: str, persona: str) -> None:
    """Add or update a character in project.json."""
    from audioformation.project import load_project_json, save_project_json

    if not _project_guard(project_id):
        return

    pj = load_project_json(project_id)
    
    char_entry = {
        "name": name,
        "engine": engine,
        "voice": voice,
        "dialect": dialect,
        "persona": persona,
        "reference_audio": None
    }

    # If updating, preserve existing fields if not overwritten
    if char_id in pj.get("characters", {}):
        existing = pj["characters"][char_id]
        if not voice and existing.get("voice"):
            char_entry["voice"] = existing["voice"]
        if not persona and existing.get("persona"):
            char_entry["persona"] = existing["persona"]
        if existing.get("reference_audio"):
            char_entry["reference_audio"] = existing["reference_audio"]
        action = "Updated"
    else:
        action = "Added"

    pj.setdefault("characters", {})[char_id] = char_entry
    save_project_json(project_id, pj)

    click.secho(f"✓ {action} character: {char_id}", fg="green")


@cast.command("clone")
@click.argument("project_id")
@click.option("--id", "char_id", required=True, help="Character ID.")
@click.option("--reference", type=click.Path(exists=True, path_type=Path), required=True,
              help="Path to reference audio file.")
@click.option("--name", default=None, help="Character name (optional if exists).")
def cast_clone(project_id: str, char_id: str, reference: Path, name: str | None) -> None:
    """
    Setup voice cloning: copy audio ref and set engine to XTTS.
    """
    from audioformation.project import load_project_json, save_project_json, get_project_path
    from audioformation.utils.security import sanitize_filename

    if not _project_guard(project_id):
        return

    project_path = get_project_path(project_id)
    voices_dir = project_path / "02_VOICES" / "references"
    voices_dir.mkdir(parents=True, exist_ok=True)

    # Copy file
    safe_name = sanitize_filename(reference.name)
    dest_path = voices_dir / safe_name
    shutil.copy2(reference, dest_path)
    
    # Relative path for project.json
    rel_path = f"02_VOICES/references/{safe_name}"

    pj = load_project_json(project_id)
    characters = pj.setdefault("characters", {})

    if char_id in characters:
        char_data = characters[char_id]
        char_data["engine"] = "xtts"
        char_data["reference_audio"] = rel_path
        # Clear voice ID since we are using reference
        char_data["voice"] = None
        if name:
            char_data["name"] = name
        action = "Updated"
    else:
        if not name:
            name = char_id.title()
        char_data = {
            "name": name,
            "engine": "xtts",
            "voice": None,
            "dialect": "msa",
            "persona": "Voice clone",
            "reference_audio": rel_path
        }
        characters[char_id] = char_data
        action = "Created"

    save_project_json(project_id, pj)

    click.secho(f"✓ Copied reference to: {rel_path}", fg="green")
    click.secho(f"✓ {action} character '{char_id}' using XTTS engine.", fg="green")


# ──────────────────────────────────────────────
# SFX Management (FXForge)
# ──────────────────────────────────────────────


@main.group()
def sfx() -> None:
    """FXForge: Procedural sound effects."""
    pass


@sfx.command("generate")
@click.argument("project_id")
@click.option("--type", "sfx_type", type=click.Choice(["whoosh", "impact", "ui_click", "static", "drone"]), required=True)
@click.option("--duration", type=float, default=1.0, help="Duration in seconds.")
@click.option("--name", "filename", default=None, help="Output filename (optional).")
def sfx_generate(project_id: str, sfx_type: str, duration: float, filename: str | None) -> None:
    """Generate a procedural sound effect."""
    from audioformation.project import get_project_path
    from audioformation.audio.sfx import generate_sfx

    if not _project_guard(project_id):
        return

    project_path = get_project_path(project_id)
    sfx_dir = project_path / "04_SFX" / "procedural"
    sfx_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = str(int(time.time()))
        filename = f"{sfx_type}_{timestamp}.wav"
    
    output_path = sfx_dir / filename

    try:
        generate_sfx(sfx_type, output_path=output_path, duration=duration)
        click.secho(f"✓ Generated {sfx_type}: {output_path.name}", fg="green")
    except Exception as e:
        click.secho(f"✗ Failed: {e}", fg="red")
        sys.exit(1)


# ──────────────────────────────────────────────
# Pipeline execution
# ──────────────────────────────────────────────


@main.command()
@click.argument("project_id")
def validate(project_id: str) -> None:
    """Run validation gate (Node 2) on a project."""
    from audioformation.validation import validate_project
    from audioformation.pipeline import update_node_status

    if not _project_guard(project_id):
        return

    click.echo(f"Validating project: {project_id}")
    click.echo()

    result = validate_project(project_id)
    summary = result.summary()

    for msg in summary["details"]["passed"]:
        click.echo(f"  {click.style('✓', fg='green')} {msg}")
    for msg in summary["details"]["warnings"]:
        click.echo(f"  {click.style('⚠', fg='yellow')} {msg}")
    for msg in summary["details"]["failures"]:
        click.echo(f"  {click.style('✗', fg='red')} {msg}")

    click.echo()
    click.echo(
        f"Results: {summary['passed']} passed, "
        f"{summary['warnings']} warnings, "
        f"{summary['failures']} failures"
    )

    if result.ok:
        click.secho("✓ Validation PASSED", fg="green", bold=True)
        update_node_status(project_id, "validate", "complete")
    else:
        click.secho("✗ Validation FAILED — fix issues and retry", fg="red", bold=True)
        update_node_status(project_id, "validate", "failed")
        sys.exit(1)


@main.command()
@click.argument("project_id")
@click.option("--source", type=click.Path(exists=True, path_type=Path), required=True,
              help="Directory containing .txt chapter files.")
@click.option("--language", type=str, default=None,
              help="Override language for all files (ar/en). Auto-detects if omitted.")
def ingest(project_id: str, source: Path, language: str | None) -> None:
    """Import text files into a project (Node 1)."""
    from audioformation.ingest import ingest_text
    from audioformation.project import get_project_path

    if not _project_guard(project_id):
        return

    click.echo(f"Ingesting text from: {source}")

    try:
        result = ingest_text(project_id, source, language=language)
    except (FileNotFoundError, ValueError) as e:
        click.secho(f"✗ {e}", fg="red")
        sys.exit(1)

    click.echo()
    for detail in result["details"]:
        if detail["status"] == "ingested":
            lang = detail.get("language", "?")
            chars = detail.get("characters", 0)
            diacrit = detail.get("diacritization", "")
            diacrit_str = f" [{diacrit}]" if diacrit else ""
            click.echo(
                f"  {click.style('✓', fg='green')} {detail['file']} → "
                f"{detail['chapter_id']} ({lang}, {chars} chars{diacrit_str})"
            )
        else:
            click.echo(
                f"  {click.style('⊘', fg='white')} {detail['file']} — "
                f"{detail.get('reason', 'skipped')}"
            )

    click.echo()
    click.secho(
        f"✓ Ingested {result['ingested']} files, skipped {result['skipped']}.",
        fg="green",
    )
    
    # Write pipeline status — ingest complete
    project_path = get_project_path(project_id)
    mark_node(project_path, "ingest", "complete", files_ingested=result["ingested"])
    
    click.echo(f"  Next: audioformation validate {project_id}")


@main.command()
@click.argument("project_id")
@click.option("--engine", type=str, default=None,
              help="Override TTS engine (edge, xtts, elevenlabs).")
@click.option("--device", type=click.Choice(["gpu", "cpu"]), default=None,
              help="Device for XTTS.")
@click.option("--chapters", type=str, default=None,
              help="Comma-separated chapter IDs to generate. Default: all.")
def generate(project_id: str, engine: str | None, device: str | None, chapters: str | None) -> None:
    """Run TTS generation (Node 3)."""
    from audioformation.generate import generate_project
    from audioformation.pipeline import can_proceed_to

    if not _project_guard(project_id):
        return

    # Check gate
    can, reason = can_proceed_to(project_id, "generate")
    if not can:
        click.secho(f"✗ Cannot generate: {reason}", fg="red")
        click.echo("  Run: audioformation validate " + project_id)
        sys.exit(1)

    chapter_list = [c.strip() for c in chapters.split(",")] if chapters else None

    click.echo(f"Generating audio for: {project_id}")
    if engine:
        click.echo(f"  Engine: {engine}")
    if chapter_list:
        click.echo(f"  Chapters: {', '.join(chapter_list)}")
    click.echo()

    def _cli_progress(msg: str):
        click.echo(msg)

    try:
        result = _run_async(generate_project(
            project_id,
            engine_name=engine,
            device=device,
            chapters=chapter_list,
            progress_callback=_cli_progress,
        ))
    except Exception as e:
        click.secho(f"✗ Generation error: {e}", fg="red")
        sys.exit(1)

    # Display results
    for detail in result.get("details", []):
        ch_id = detail["chapter_id"]
        ch_status = detail["status"]
        total = detail.get("total_chunks", 0)
        failed = detail.get("failed_chunks", 0)

        if ch_status == "complete":
            icon = click.style("✓", fg="green")
        elif ch_status == "partial":
            icon = click.style("◐", fg="yellow")
        else:
            icon = click.style("✗", fg="red")

        click.echo(f"  {icon} {ch_id}: {total} chunks, {failed} failed")

    click.echo()
    fail_rate = result.get("fail_rate_percent", 0)
    if fail_rate == 0:
        click.secho("✓ Generation complete.", fg="green", bold=True)
    elif fail_rate <= 5:
        click.secho(f"✓ Generation complete with {fail_rate:.1f}% failures.", fg="yellow")
    else:
        click.secho(f"✗ Generation had {fail_rate:.1f}% failures — review QC report.", fg="red")
        sys.exit(1)

    click.echo(f"  Next: audioformation qc {project_id} --report")


@main.command()
@click.argument("project_id")
@click.option("--report", is_flag=True, help="Print QC report summary.")
def qc(project_id: str, report: bool) -> None:
    """View QC scan results (Node 3.5)."""
    from audioformation.project import get_project_path

    if not _project_guard(project_id):
        return

    project_path = get_project_path(project_id)
    gen_dir = project_path / "03_GENERATED"

    # Find QC reports
    reports = sorted(gen_dir.glob("qc_report*.json"))

    if not reports:
        click.echo("No QC reports found. Run generation first.")
        click.echo(f"  audioformation generate {project_id}")
        return

    all_reports = []  # Collect all report data

    for report_path in reports:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        all_reports.append(data)

        click.secho(f"QC Report: {report_path.name}", bold=True)
        click.echo(f"  Chunks:  {data.get('total_chunks', 0)}")
        click.echo(f"  Passed:  {data.get('passed', 0)}")
        click.echo(f"  Warns:   {data.get('warnings', 0)}")
        click.echo(f"  Failed:  {data.get('failures', 0)}")
        click.echo(f"  Fail %:  {data.get('fail_rate_percent', 0):.1f}%")

        if report:
            click.echo()
            for chunk in data.get("chunks", []):
                status = chunk.get("status", "pass")
                if status == "fail":
                    click.echo(f"    {click.style('✗', fg='red')} {chunk['chunk_id']}")
                    for check_name, check_data in chunk.get("checks", {}).items():
                        if check_data.get("status") == "fail":
                            click.echo(f"      └─ {check_name}: {check_data.get('message', '')}")
                elif status == "warn":
                    click.echo(f"    {click.style('⚠', fg='yellow')} {chunk['chunk_id']}")
                    for check_name, check_data in chunk.get("checks", {}).items():
                        if check_data.get("status") == "warn":
                            click.echo(f"      └─ {check_name}: {check_data.get('message', '')}")

        click.echo()

    # Write pipeline status — qc_scan
    from audioformation.pipeline import mark_node
    
    # Calculate overall result
    total_chunks = sum(r.get("total_chunks", 0) for r in all_reports)
    total_failed = sum(r.get("failures", 0) for r in all_reports)
    fail_pct = (total_failed / total_chunks * 100) if total_chunks > 0 else 0
    
    qc_status = "failed" if fail_pct > 5 else "complete"
    mark_node(project_path, "qc_scan", qc_status, 
              chunks_scanned=total_chunks, fail_percent=round(fail_pct, 1))

@main.command("process")
@click.argument("project_id")
def process_audio(project_id: str) -> None:
    """Normalize and trim generated audio (Node 4)."""
    from audioformation.project import get_project_path, load_project_json
    from audioformation.audio.processor import normalize_lufs, trim_silence
    from audioformation.pipeline import update_node_status

    if not _project_guard(project_id):
        return

    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    target_lufs = pj.get("mix", {}).get("target_lufs", -16.0)
    true_peak = pj.get("mix", {}).get("true_peak_limit_dbtp", -1.0)

    raw_dir = project_path / "03_GENERATED" / "raw"
    processed_dir = project_path / "03_GENERATED" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Find stitched chapter WAVs (ch01.wav, ch01_intro.wav — NOT ch01_000.wav chunks)
    # Chunk files have numeric suffix after underscore (ch01_000, ch01_001)
    def _is_chunk_file(f: Path) -> bool:
        """Check if file is a chunk file (has numeric suffix after underscore)."""
        if "_" not in f.stem:
            return False
        parts = f.stem.rsplit("_", 1)
        return len(parts) == 2 and parts[1].isdigit()

    chapter_wavs = sorted(
        f for f in raw_dir.glob("ch*.wav")
        if not _is_chunk_file(f)  # Exclude chunk files only
    )

    if not chapter_wavs:
        click.secho("✗ No stitched chapter files found in raw/", fg="red")
        click.echo("  Run: audioformation generate " + project_id)
        sys.exit(1)

    click.echo(f"Processing {len(chapter_wavs)} chapter files...")
    click.echo(f"  Target LUFS: {target_lufs}")
    click.echo()

    update_node_status(project_id, "process", "running")

    success_count = 0
    for wav_path in chapter_wavs:
        output_path = processed_dir / wav_path.name
        trimmed_path = processed_dir / f"{wav_path.stem}_trimmed.wav"

        # Trim silence first
        trim_ok = trim_silence(wav_path, trimmed_path)
        source = trimmed_path if trim_ok and trimmed_path.exists() else wav_path

        # Normalize
        norm_ok = normalize_lufs(source, output_path, target_lufs=target_lufs, true_peak=true_peak)

        if norm_ok:
            click.echo(f"  {click.style('✓', fg='green')} {wav_path.name}")
            success_count += 1
        else:
            click.echo(f"  {click.style('✗', fg='red')} {wav_path.name} — normalization failed")

        # Clean up temp trimmed file
        if trimmed_path.exists() and trimmed_path != output_path:
            trimmed_path.unlink()

    click.echo()
    if success_count == len(chapter_wavs):
        click.secho("✓ Processing complete.", fg="green", bold=True)
        update_node_status(project_id, "process", "complete")
    else:
        click.secho(f"⚠ Processed {success_count}/{len(chapter_wavs)} files.", fg="yellow")
        update_node_status(project_id, "process", "partial")

    click.echo(f"  Output: {processed_dir}")


@main.command("compose")
@click.argument("project_id")
@click.option("--preset", default="contemplative", help="Mood preset (contemplative, tense, wonder, etc.)")
@click.option("--duration", type=float, default=60.0, help="Duration in seconds (default: 60)")
@click.option("--output", "output_filename", default=None, help="Output filename (optional)")
@click.option("--list", "list_only", is_flag=True, help="List available presets and exit")
def compose(project_id: str, preset: str, duration: float, output_filename: str | None, list_only: bool) -> None:
    """Generate ambient pad music (Node 5)."""
    from audioformation.audio.composer import generate_pad, list_presets
    from audioformation.project import get_project_path
    from audioformation.pipeline import mark_node

    if not _project_guard(project_id):
        return

    if list_only:
        presets = list_presets()
        click.echo("Available presets:")
        for p in presets:
            click.echo(f"  • {p}")
        return

    click.echo(f"Generating ambient pad for: {project_id}")
    click.echo(f"  Preset:   {preset}")
    click.echo(f"  Duration: {duration}s")

    project_path = get_project_path(project_id)
    music_dir = project_path / "05_MUSIC" / "generated"
    music_dir.mkdir(parents=True, exist_ok=True)

    if not output_filename:
        timestamp = str(int(time.time()))
        output_filename = f"{preset}_{timestamp}.wav"
    
    output_path = music_dir / output_filename

    try:
        generate_pad(preset, duration_sec=duration, output_path=output_path)
    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"✗ Generation failed: {e}", fg="red")
        sys.exit(1)

    click.secho(f"✓ Saved: {output_path.name}", fg="green")
    
    # Update pipeline status
    mark_node(project_path, "compose", "complete", preset=preset, duration=duration)


@main.command("mix")
@click.argument("project_id")
@click.option("--music", "music_file", default=None, help="Optional: Background music file (in 05_MUSIC/generated).")
def mix(project_id: str, music_file: str | None) -> None:
    """Mix voice and music with ducking (Node 6)."""
    from audioformation.mix import mix_project
    from audioformation.pipeline import can_proceed_to

    if not _project_guard(project_id):
        return

    # Check gates
    can, reason = can_proceed_to(project_id, "mix")
    if not can:
        click.secho(f"✗ Cannot start mixing: {reason}", fg="red")
        sys.exit(1)

    click.echo(f"Starting mix for project: {project_id}")
    
    def _cli_progress(msg: str):
        # Naive color mapping
        if "✗" in msg:
            click.secho(msg, fg="red")
        elif "✓" in msg:
            click.secho(msg, fg="green", bold=True)
        elif "⚠" in msg:
            click.secho(msg, fg="yellow")
        else:
            click.echo(msg)

    success = mix_project(project_id, music_file, progress_callback=_cli_progress)
    
    if not success:
        sys.exit(1)


@main.command("qc-final")
@click.argument("project_id")
def qc_final(project_id: str) -> None:
    """Run Final QC on mixed audio (Node 7)."""
    from audioformation.qc.final import scan_final_mix
    from audioformation.pipeline import can_proceed_to

    if not _project_guard(project_id):
        return

    # Gates check
    can, reason = can_proceed_to(project_id, "qc_final")
    if not can:
        click.secho(f"✗ Cannot run QC Final: {reason}", fg="red")
        sys.exit(1)

    click.echo(f"Running QC Final for: {project_id}")
    
    report = scan_final_mix(project_id)
    
    click.echo()
    click.secho("QC Final Report", bold=True)
    click.echo(f"  Target LUFS: {report.target_lufs} (±1.0)")
    click.echo(f"  Limit True Peak: {report.true_peak_limit} dBTP")
    click.echo("-" * 60)
    
    for res in report.results:
        status_icon = click.style("✓", fg="green") if res.status == "pass" else click.style("✗", fg="red")
        click.echo(f"  {status_icon} {res.filename:<25} "
                   f"LUFS: {res.lufs:>5.1f}  TP: {res.true_peak:>5.1f}")
        
        if res.status == "fail":
            for msg in res.messages:
                click.echo(f"      └─ {msg}")

    click.echo("-" * 60)
    
    if report.passed:
        click.secho("✓ QC Final PASSED. Ready for export.", fg="green", bold=True)
    else:
        click.secho("✗ QC Final FAILED. Adjust mix settings and retry.", fg="red", bold=True)
        sys.exit(1)


@main.command("export")
@click.argument("project_id")
@click.option("--format", "fmt", type=click.Choice(["mp3", "wav", "m4b"]), default="mp3",
              help="Export format.")
@click.option("--bitrate", type=int, default=None,
              help="MP3 bitrate in kbps (default: from project.json).")
def export_audio(project_id: str, fmt: str, bitrate: int | None) -> None:
    """Export final audio files (Node 8)."""
    from audioformation.project import get_project_path, load_project_json
    from audioformation.export.mp3 import export_mp3, export_wav
    from audioformation.export.m4b import export_project_m4b
    from audioformation.export.metadata import generate_manifest
    from audioformation.pipeline import update_node_status, can_proceed_to

    if not _project_guard(project_id):
        return

    # Verify gates (including QC Final)
    can, reason = can_proceed_to(project_id, "export")
    if not can:
        click.secho(f"✗ Cannot export: {reason}", fg="red")
        click.echo("  Run: audioformation qc-final " + project_id)
        sys.exit(1)

    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    export_config = pj.get("export", {})

    export_dir = project_path / "07_EXPORT"
    
    # ── M4B / Audiobook Export ──
    if fmt == "m4b":
        click.echo("Exporting full audiobook as M4B...")
        audiobook_dir = export_dir / "audiobook"
        audiobook_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine filename
        filename = f"{project_id}.m4b"
        out_path = audiobook_dir / filename
        
        # Run export
        update_node_status(project_id, "export", "running", mode="m4b")
        ok = export_project_m4b(project_id, out_path, bitrate=export_config.get("m4b_aac_bitrate", 128))
        
        if ok:
            click.secho(f"✓ Created: {out_path}", fg="green", bold=True)
            update_node_status(project_id, "export", "complete", mode="m4b")
        else:
            click.secho("✗ M4B export failed.", fg="red")
            update_node_status(project_id, "export", "failed")
            
        return

    # ── Chapter-based Export (MP3/WAV) ──
    
    # Source: Mixed files from 06_MIX/renders
    mix_dir = project_path / "06_MIX" / "renders"
    
    if not mix_dir.exists() or not list(mix_dir.glob("*.wav")):
        click.secho("✗ No mixed audio files found in 06_MIX/renders/.", fg="red")
        click.echo("  Run: audioformation mix " + project_id)
        sys.exit(1)

    chapter_files = sorted(mix_dir.glob("*.wav"))

    chapters_dir = export_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    update_node_status(project_id, "export", "running")

    mp3_bitrate = bitrate or export_config.get("mp3_bitrate", 192)

    click.echo(f"Exporting {len(chapter_files)} chapters as {fmt.upper()}...")
    click.echo()

    success_count = 0
    for wav_path in chapter_files:
        if fmt == "mp3":
            out_path = chapters_dir / f"{wav_path.stem}.mp3"
            ok = export_mp3(wav_path, out_path, bitrate=mp3_bitrate)
        elif fmt == "wav":
            out_path = chapters_dir / f"{wav_path.stem}.wav"
            ok = export_wav(wav_path, out_path)
        else:
            ok = False

        if ok:
            click.echo(f"  {click.style('✓', fg='green')} {out_path.name}")
            success_count += 1
        else:
            click.echo(f"  {click.style('✗', fg='red')} {wav_path.stem} — export failed")

    # Generate manifest
    click.echo()
    click.echo("Generating manifest...")
    manifest_path = generate_manifest(
        export_dir,
        project_id,
        metadata=export_config.get("metadata", {}),
    )
    click.echo(f"  {click.style('✓', fg='green')} {manifest_path.name}")

    click.echo()
    if success_count == len(chapter_files):
        click.secho("✓ Export complete.", fg="green", bold=True)
        update_node_status(project_id, "export", "complete")
    else:
        click.secho(f"⚠ Exported {success_count}/{len(chapter_files)} files.", fg="yellow")
        update_node_status(project_id, "export", "partial")

    click.echo(f"  Output: {export_dir}")


# ──────────────────────────────────────────────
# Quick generation (no project)
# ──────────────────────────────────────────────


@main.command()
@click.argument("text", required=False)
@click.option("--engine", type=str, default="edge", help="TTS engine.")
@click.option("--voice", type=str, default="ar-SA-HamedNeural", help="Voice ID.")
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None,
              help="Output file path.")
def quick(text: str | None, engine: str, voice: str, output: Path | None) -> None:
    """Quick TTS generation without a project."""
    import sys as _sys

    # Read from stdin if no text argument
    if not text:
        if not _sys.stdin.isatty():
            text = _sys.stdin.read().strip()
        else:
            click.secho("✗ No text provided. Pass as argument or pipe via stdin.", fg="red")
            sys.exit(1)

    if not text:
        click.secho("✗ Empty text.", fg="red")
        sys.exit(1)

    from audioformation.engines.registry import registry
    from audioformation.engines.base import GenerationRequest

    # Default output path
    if output is None:
        output = Path("quick_output.mp3")

    # Use WAV for generation, then convert if needed
    wav_output = output.with_suffix(".wav") if output.suffix != ".wav" else output

    click.echo(f"Generating: \"{text[:60]}{'...' if len(text) > 60 else ''}\"")
    click.echo(f"  Engine: {engine}")
    click.echo(f"  Voice:  {voice}")

    try:
        tts = registry.get(engine)
    except KeyError as e:
        click.secho(f"✗ {e}", fg="red")
        sys.exit(1)

    request = GenerationRequest(
        text=text,
        output_path=wav_output,
        voice=voice,
    )

    result = _run_async(tts.generate(request))

    if not result.success:
        click.secho(f"✗ Generation failed: {result.error}", fg="red")
        sys.exit(1)

    # Convert to target format if needed
    if output.suffix == ".mp3":
        from audioformation.export.mp3 import export_mp3
        ok = export_mp3(wav_output, output, bitrate=192)
        if ok and wav_output != output:
            wav_output.unlink(missing_ok=True)
        elif not ok:
            click.secho("✗ MP3 conversion failed. WAV saved instead.", fg="yellow")
            output = wav_output

    click.secho(f"✓ Saved: {output}", fg="green")
    click.echo(f"  Duration: {result.duration_sec:.1f}s")


# ──────────────────────────────────────────────
# Preview & Compare (Phase 2)
# ──────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.argument("chapter_id")
@click.option("--duration", type=float, default=30.0, help="Preview duration in seconds (default: 30).")
@click.option("--chars", type=int, default=None, help="Preview length in characters (overrides duration).")
@click.option("--engine", type=str, default=None, help="Override TTS engine.")
@click.option("--voice", type=str, default=None, help="Override voice ID.")
def preview(project_id: str, chapter_id: str, duration: float, chars: int | None, engine: str | None, voice: str | None) -> None:
    """Generate a quick preview of a chapter."""
    from audioformation.project import get_project_path, load_project_json
    from audioformation.engines.registry import registry
    from audioformation.engines.base import GenerationRequest

    if not _project_guard(project_id):
        return

    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    
    # Find chapter
    chapter = next((c for c in pj.get("chapters", []) if c["id"] == chapter_id), None)
    if not chapter:
        click.secho(f"✗ Chapter '{chapter_id}' not found.", fg="red")
        sys.exit(1)

    # Load source text
    source_path = project_path / chapter.get("source", "")
    if not source_path.exists():
        click.secho(f"✗ Source file not found: {source_path}", fg="red")
        sys.exit(1)
        
    text = source_path.read_text(encoding="utf-8").strip()
    
    # Truncate text for preview
    # Approx 15 chars per second for speech
    preview_chars = chars or int(duration * 15)
    if len(text) > preview_chars:
        # Cut at last space to be clean
        cut_point = text[:preview_chars].rfind(" ")
        if cut_point > 0:
            text = text[:cut_point] + "..."
        else:
            text = text[:preview_chars] + "..."

    # Determine character/engine
    char_id = chapter.get("character", "narrator")
    char_data = pj.get("characters", {}).get(char_id, {})
    
    target_engine = engine or char_data.get("engine", "edge")
    target_voice = voice or char_data.get("voice")
    
    click.echo(f"Generating preview for {project_id}/{chapter_id}")
    click.echo(f"  Engine: {target_engine}")
    click.echo(f"  Voice:  {target_voice}")
    click.echo(f"  Length: {len(text)} chars (~{len(text)/15:.1f}s)")
    
    try:
        tts = registry.get(target_engine)
    except KeyError:
        click.secho(f"✗ Engine '{target_engine}' not available.", fg="red")
        sys.exit(1)

    # Output path
    preview_dir = project_path / "03_GENERATED" / "compare"
    preview_dir.mkdir(parents=True, exist_ok=True)
    timestamp = str(int(time.time()))
    output_path = preview_dir / f"preview_{chapter_id}_{timestamp}.wav"

    request = GenerationRequest(
        text=text,
        output_path=output_path,
        voice=target_voice,
        language=chapter.get("language", "ar"),
        # Use simple single-request generation for preview (no chunking)
    )

    # Run generation
    try:
        result = _run_async(tts.generate(request))
        if result.success:
            click.secho(f"✓ Saved preview: {output_path.name}", fg="green")
            click.echo(f"  Path: {output_path}")
        else:
            click.secho(f"✗ Preview failed: {result.error}", fg="red")
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red")


@main.command()
@click.argument("project_id")
@click.argument("chapter_id")
@click.option("--engines", type=str, default="edge,gtts", help="Comma-separated engines to compare.")
def compare(project_id: str, chapter_id: str, engines: str) -> None:
    """Generate A/B comparisons using multiple engines."""
    # Re-use preview logic loop
    engine_list = [e.strip() for e in engines.split(",")]
    
    click.echo(f"Comparing engines: {', '.join(engine_list)}")
    
    ctx = click.get_current_context()
    for eng in engine_list:
        click.echo(f"\n--- {eng} ---")
        ctx.invoke(preview, project_id=project_id, chapter_id=chapter_id, engine=eng, duration=30.0, chars=None, voice=None)


# ──────────────────────────────────────────────
# Engine management
# ──────────────────────────────────────────────


@main.group()
def engines() -> None:
    """Manage TTS engines."""
    pass


@engines.command("list")
def engines_list() -> None:
    """List available TTS engines."""
    from audioformation.engines.registry import registry

    available = registry.list_available()

    click.secho("Available Engines:", bold=True)
    for name in available:
        engine = registry.get(name)
        features = []
        if engine.supports_cloning:
            features.append("cloning")
        if engine.supports_ssml:
            features.append("SSML")
        if engine.requires_gpu:
            features.append("GPU")

        feature_str = f" ({', '.join(features)})" if features else ""
        click.echo(f"  • {name}{feature_str}")


@engines.command("test")
@click.argument("engine_name")
@click.option("--device", type=click.Choice(["gpu", "cpu"]), default=None)
def engines_test(engine_name: str, device: str | None) -> None:
    """Test if a TTS engine is available and functional."""
    from audioformation.engines.registry import registry

    try:
        engine = registry.get(engine_name)
    except KeyError as e:
        click.secho(f"✗ {e}", fg="red")
        sys.exit(1)

    click.echo(f"Testing engine: {engine_name}...")

    ok = _run_async(engine.test_connection())

    if ok:
        click.secho(f"✓ {engine_name} is available.", fg="green")
    else:
        click.secho(f"✗ {engine_name} is NOT available.", fg="red")
        sys.exit(1)


@engines.command("voices")
@click.argument("engine_name")
@click.option("--lang", type=str, default=None, help="Filter by language prefix (e.g., 'ar').")
def engines_voices(engine_name: str, lang: str | None) -> None:
    """List voices available on an engine."""
    from audioformation.engines.registry import registry

    try:
        engine = registry.get(engine_name)
    except KeyError as e:
        click.secho(f"✗ {e}", fg="red")
        sys.exit(1)

    voices = _run_async(engine.list_voices(language=lang))

    if not voices:
        click.echo(f"No voices found for engine '{engine_name}'" +
                    (f" with language '{lang}'" if lang else "") + ".")
        return

    click.echo(f"{'ID':<35} {'Name':<40} {'Locale':<10} {'Gender'}")
    click.echo("─" * 95)

    for v in voices:
        click.echo(
            f"{v.get('id', ''):<35} "
            f"{v.get('name', ''):<40} "
            f"{v.get('locale', ''):<10} "
            f"{v.get('gender', '')}"
        )

    click.echo(f"\nTotal: {len(voices)} voices")


# ──────────────────────────────────────────────
# Full pipeline run
# ──────────────────────────────────────────────


@main.command()
@click.argument("project_id")
@click.option("--all", "run_all", is_flag=True, help="Run complete pipeline.")
@click.option("--from", "from_node", type=str, default=None,
              help="Resume from a specific node.")
@click.option("--dry-run", is_flag=True, help="Estimate time and cost without generating.")
@click.option("--engine", type=str, default=None, help="Override TTS engine.")
def run(project_id: str, run_all: bool, from_node: str | None, dry_run: bool, engine: str | None) -> None:
    """Run the full pipeline or resume from a node."""
    from audioformation.pipeline import get_resume_point, nodes_in_range

    if not _project_guard(project_id):
        return

    if dry_run:
        _dry_run(project_id, engine)
        return

    if not run_all and not from_node:
        click.echo("Specify --all or --from <node>.")
        click.echo(f"  Nodes: {', '.join(PIPELINE_NODES)}")
        sys.exit(1)

    start_node = get_resume_point(project_id, from_node) if from_node else PIPELINE_NODES[0]
    nodes = nodes_in_range(start_node)

    click.secho(f"Running pipeline: {project_id}", fg="cyan", bold=True)
    click.echo(f"  Nodes: {' → '.join(nodes)}")
    click.echo()

    # Execute nodes by invoking the corresponding CLI commands
    ctx = click.get_current_context()

    for node in nodes:
        click.secho(f"── Node: {node} ──", fg="cyan")

        if node == "bootstrap":
            click.echo("  Already complete (project exists).")
            from audioformation.pipeline import update_node_status
            update_node_status(project_id, "bootstrap", "complete")

        elif node == "ingest":
            click.echo("  Skipping ingest — run manually with --source.")
            click.echo(f"  audioformation ingest {project_id} --source ./chapters/")

        elif node == "validate":
            ctx.invoke(validate, project_id=project_id)

        elif node == "generate":
            ctx.invoke(generate, project_id=project_id, engine=engine, device=None, chapters=None)

        elif node == "qc_scan":
            click.echo("  QC scan runs automatically during generation.")
            from audioformation.pipeline import update_node_status
            update_node_status(project_id, "qc_scan", "complete")

        elif node == "process":
            ctx.invoke(process_audio, project_id=project_id)

        elif node == "compose":
            ctx.invoke(compose, project_id=project_id, preset="contemplative", duration=60.0, output_filename=None, list_only=False)

        elif node == "mix":
            ctx.invoke(mix, project_id=project_id, music_file=None)

        elif node == "qc_final":
            ctx.invoke(qc_final, project_id=project_id)

        elif node == "export":
            ctx.invoke(export_audio, project_id=project_id, fmt="mp3", bitrate=None)

        click.echo()


def _dry_run(project_id: str, engine_name: str | None) -> None:
    """Estimate generation time, chunk count, and cost."""
    from audioformation.project import load_project_json, get_project_path
    from audioformation.utils.text import chunk_text

    pj = load_project_json(project_id)
    project_path = get_project_path(project_id)
    gen_config = pj.get("generation", {})
    max_chars = gen_config.get("chunk_max_chars", 200)
    strategy = gen_config.get("chunk_strategy", "breath_group")

    chapters = pj.get("chapters", [])
    total_chunks = 0
    total_chars = 0

    click.secho(f"Dry Run: {project_id}", fg="cyan", bold=True)
    click.echo()

    for ch in chapters:
        source = ch.get("source", "")
        source_path = project_path / source

        if source_path.exists():
            text = source_path.read_text(encoding="utf-8").strip()
            chunks = chunk_text(text, max_chars=max_chars, strategy=strategy)
            total_chunks += len(chunks)
            total_chars += len(text)

            char_id = ch.get("character", "narrator")
            char_data = pj.get("characters", {}).get(char_id, {})
            eng = engine_name or char_data.get("engine", "edge")

            click.echo(
                f"  {ch['id']}: {len(text)} chars → "
                f"{len(chunks)} chunks ({eng})"
            )
        else:
            click.echo(f"  {ch['id']}: source file not found")

    click.echo()
    click.echo(f"  Total characters: {total_chars:,}")
    click.echo(f"  Total chunks:     {total_chunks}")

    # Time estimates
    edge_time = total_chunks * 2  # ~2s per chunk for edge-tts
    xtts_gpu_time = total_chunks * 5  # ~5s per chunk for XTTS GPU
    xtts_cpu_time = total_chunks * 20  # ~20s per chunk for XTTS CPU

    click.echo()
    click.echo("  Estimated generation time:")
    click.echo(f"    edge-tts:  ~{_format_time(edge_time)}")
    click.echo(f"    XTTS GPU:  ~{_format_time(xtts_gpu_time)}")
    click.echo(f"    XTTS CPU:  ~{_format_time(xtts_cpu_time)}")

    # Cost estimates for cloud
    eleven_cost = total_chars * 0.00003  # ~\$30/1M chars
    click.echo()
    click.echo("  Estimated cloud costs:")
    click.echo(f"    ElevenLabs: ~${eleven_cost:.2f}")
    click.echo("    edge-tts:   $0.00 (free)")


def _format_time(seconds: int) -> str:
    """Format seconds into human-readable time string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"


# ──────────────────────────────────────────────
# Server
# ──────────────────────────────────────────────


@main.command()
@click.option("--port", type=int, default=API_PORT, help="Port to bind.")
@click.option("--host", type=str, default="0.0.0.0", help="Host to bind.")
def serve(port: int, host: str) -> None:
    """Start the AudioFormation API server."""
    try:
        import uvicorn
        import importlib.util
        if not importlib.util.find_spec("audioformation.server.app"):
            raise ImportError()
    except ImportError:
        click.secho("✗ Server dependencies not installed.", fg="red")
        click.echo("  Run: pip install \"audioformation[server]\"")
        sys.exit(1)

    click.secho(f"🚀 Starting API server on http://localhost:{port}", fg="green", bold=True)
    click.echo(f"   Docs: http://localhost:{port}/docs")
    
    uvicorn.run("audioformation.server.app:app", host=host, port=port, reload=True)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _project_guard(project_id: str) -> bool:
    """Check project exists. Returns True if OK, exits if not."""
    from audioformation.project import project_exists

    if not project_exists(project_id):
        click.secho(f"✗ Project not found: {project_id}", fg="red")
        click.echo("  Run: audioformation list")
        sys.exit(1)

    return True
