"""
Generation pipeline — run TTS per chapter with chunking, crossfade,
QC scanning, retry logic, and per-chapter engine fallback.

Pipeline Node 3: Generate.
"""

import asyncio
from pathlib import Path
from typing import Any

import click

from audioformation.config import (
    DEFAULT_CROSSFADE_MS,
    DEFAULT_LEADING_SILENCE_MS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_FAIL_THRESHOLD_PCT,
    DEFAULT_TARGET_LUFS,
)
from audioformation.project import (
    get_project_path,
    load_project_json,
)
from audioformation.pipeline import (
    update_node_status,
    update_chapter_status,
    get_node_status,
)
from audioformation.engines.base import GenerationRequest
from audioformation.engines.registry import registry
from audioformation.utils.text import chunk_text, parse_chapter_segments
from audioformation.audio.processor import crossfade_stitch
from audioformation.qc.scanner import scan_chunk, QCReport
from audioformation.qc.report import save_report


async def generate_project(
    project_id: str,
    engine_name: str | None = None,
    device: str | None = None,
    chapters: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run TTS generation for a project.

    Args:
        project_id: Target project.
        engine_name: Override engine (None = use character's engine).
        device: Device hint ('gpu', 'cpu') for XTTS.
        chapters: Specific chapter IDs to generate (None = all).

    Returns generation results dict.
    """
    project_path = get_project_path(project_id)
    pj = load_project_json(project_id)
    gen_config = pj.get("generation", {})
    qc_config = pj.get("qc", {})
    target_lufs = pj.get("mix", {}).get("target_lufs", DEFAULT_TARGET_LUFS)

    all_chapters = pj.get("chapters", [])
    if chapters:
        all_chapters = [ch for ch in all_chapters if ch["id"] in chapters]

    if not all_chapters:
        raise ValueError("No chapters to generate.")

    # Fallback configuration
    fallback_scope = gen_config.get("fallback_scope", "chapter")
    fallback_chain = gen_config.get("fallback_chain", ["edge", "gtts"])

    update_node_status(
        project_id, "generate", "running",
        engine=engine_name or "per-character",
    )

    raw_dir = project_path / "03_GENERATED" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    total_fail_chunks = 0
    total_chunks = 0
    project_engine_failed = False  # For "project" scope fallback

    for chapter in all_chapters:
        ch_id = chapter["id"]
        char_id = chapter.get("character", chapter.get("default_character", "narrator"))
        char_data = pj.get("characters", {}).get(char_id, {})

        # Determine primary engine for this chapter
        primary_engine = engine_name or char_data.get("engine", "edge")

        # Build engine attempt list for this chapter
        if project_engine_failed and fallback_scope == "project":
            # Primary is dead for entire project — start from fallback
            engines_to_try = [
                e for e in fallback_chain if e != primary_engine
            ]
            if not engines_to_try:
                engines_to_try = [primary_engine]  # last resort
        else:
            # Normal: primary first, then fallback chain
            engines_to_try = [primary_engine] + [
                e for e in fallback_chain if e != primary_engine
            ]

        ch_result = None

        for attempt_engine in engines_to_try:
            ch_result = await _generate_chapter(
                project_id=project_id,
                project_path=project_path,
                chapter=chapter,
                characters=pj.get("characters", {}),
                gen_config=gen_config,
                qc_config=qc_config,
                target_lufs=target_lufs,
                raw_dir=raw_dir,
                engine_override=attempt_engine,
            )

            if ch_result.get("status") == "complete":
                if attempt_engine != primary_engine:
                    click.echo(
                        f"    \u26a0 {ch_id}: fell back from "
                        f"{primary_engine} to {attempt_engine}"
                    )
                    if fallback_scope == "project":
                        project_engine_failed = True
                        click.echo(
                            f"    \u26a0 Project-scope fallback activated: "
                            f"switching to {attempt_engine} for remaining chapters"
                        )
                break
            else:
                # Clean up partial output before trying next engine
                _cleanup_chapter_chunks(ch_id, raw_dir)
                click.echo(
                    f"    \u2717 {ch_id}: {attempt_engine} failed "
                    f"({ch_result.get('error', 'unknown')}), "
                    f"trying next engine..."
                )
                # Mark primary as failed for project scope
                if attempt_engine == primary_engine:
                    if fallback_scope == "project":
                        project_engine_failed = True

        if ch_result is None:
            ch_result = {
                "chapter_id": ch_id,
                "status": "failed",
                "error": "No engines available",
                "total_chunks": 0,
                "failed_chunks": 0,
            }

        results.append(ch_result)
        total_fail_chunks += ch_result.get("failed_chunks", 0)
        total_chunks += ch_result.get("total_chunks", 0)

    fail_threshold = gen_config.get(
        "fail_threshold_percent", DEFAULT_FAIL_THRESHOLD_PCT
    )
    overall_fail_rate = (total_fail_chunks / max(total_chunks, 1)) * 100

    if overall_fail_rate > fail_threshold:
        update_node_status(
            project_id, "generate", "failed",
            error=(
                f"Fail rate {overall_fail_rate:.1f}% exceeds "
                f"threshold {fail_threshold}%"
            ),
        )
    else:
        all_complete = all(r.get("status") == "complete" for r in results)
        status = "complete" if all_complete else "partial"
        update_node_status(project_id, "generate", status)

    return {
        "chapters": len(results),
        "total_chunks": total_chunks,
        "failed_chunks": total_fail_chunks,
        "fail_rate_percent": round(overall_fail_rate, 2),
        "details": results,
    }


def _cleanup_chapter_chunks(chapter_id: str, raw_dir: Path) -> None:
    """Remove partial chunk files for a chapter before retry with different engine."""
    if raw_dir.exists():
        for f in raw_dir.glob(f"{chapter_id}_*.wav"):
            f.unlink(missing_ok=True)
    stitched = raw_dir / f"{chapter_id}.wav"
    stitched.unlink(missing_ok=True)


def _get_crossfade_ms(gen_config: dict, engine_name: str) -> int:
    """Get crossfade duration, checking per-engine overrides first."""
    overrides = gen_config.get("crossfade_overrides", {})
    if engine_name in overrides:
        return int(overrides[engine_name])
    return int(gen_config.get("crossfade_ms", DEFAULT_CROSSFADE_MS))


async def _generate_chapter(
    project_id: str,
    project_path: Path,
    chapter: dict[str, Any],
    characters: dict[str, Any],
    gen_config: dict[str, Any],
    qc_config: dict[str, Any],
    target_lufs: float,
    raw_dir: Path,
    engine_override: str | None = None,
) -> dict[str, Any]:
    """Generate audio for a single chapter with a single engine."""
    ch_id = chapter["id"]
    mode = chapter.get("mode", "single")
    char_id = chapter.get(
        "character", chapter.get("default_character", "narrator")
    )
    char_data = characters.get(char_id, {})
    direction = chapter.get("direction", {})
    language = chapter.get("language", "ar")

    # Load text
    source_path = project_path / chapter.get("source", "")
    if not source_path.exists():
        update_chapter_status(
            project_id, ch_id, "failed", error="Source file not found."
        )
        return {
            "chapter_id": ch_id,
            "status": "failed",
            "error": "Source file not found.",
            "total_chunks": 0,
            "failed_chunks": 0,
        }

    text = source_path.read_text(encoding="utf-8").strip()

    # Parse segments
    segments = parse_chapter_segments(
        text, mode=mode, default_character=char_id
    )

    # Determine engine
    engine_name = engine_override or char_data.get("engine", "edge")
    try:
        engine = registry.get(engine_name)
    except KeyError as e:
        error_msg = f"Engine not available: {e}"
        update_chapter_status(project_id, ch_id, "failed", error=error_msg)
        return {
            "chapter_id": ch_id,
            "status": "failed",
            "error": error_msg,
            "total_chunks": 0,
            "failed_chunks": 0,
        }

    # Chunking config
    max_chars = gen_config.get("chunk_max_chars", 200)
    strategy = gen_config.get("chunk_strategy", "breath_group")
    crossfade_ms = _get_crossfade_ms(gen_config, engine_name)
    leading_silence_ms = gen_config.get(
        "leading_silence_ms", DEFAULT_LEADING_SILENCE_MS
    )
    max_retries = gen_config.get(
        "max_retries_per_chunk", DEFAULT_MAX_RETRIES
    )
    use_ssml = (
        gen_config.get("edge_tts_ssml", True) and engine.supports_ssml
    )

    # Generate chunks for each segment
    chunk_paths: list[Path] = []
    qc_report = QCReport(project_id=project_id, chapter_id=ch_id)
    chunk_index = 0
    failed_chunks = 0

    for segment in segments:
        chunks = chunk_text(
            segment.text, max_chars=max_chars, strategy=strategy
        )

        for chunk_text_item in chunks:
            chunk_id = f"{ch_id}_{chunk_index:03d}"
            chunk_path = raw_dir / f"{chunk_id}.wav"

            success = False
            last_error = ""

            for attempt in range(max_retries + 1):
                request = GenerationRequest(
                    text=chunk_text_item,
                    output_path=chunk_path,
                    voice=char_data.get("voice"),
                    language=language,
                    reference_audio=(
                        project_path / char_data["reference_audio"]
                        if char_data.get("reference_audio")
                        else None
                    ),
                    direction=direction if use_ssml else None,
                    params={
                        "ssml": use_ssml,
                        "temperature": gen_config.get("xtts_temperature", 0.7),
                        "repetition_penalty": gen_config.get(
                            "xtts_repetition_penalty", 5.0
                        ),
                    },
                )

                result = await engine.generate(request)

                if (
                    result.success
                    and chunk_path.exists()
                    and chunk_path.stat().st_size > 0
                ):
                    # QC scan this chunk
                    qc_result = scan_chunk(
                        chunk_path,
                        chunk_id,
                        qc_config,
                        target_lufs=target_lufs,
                    )
                    qc_report.chunks.append(qc_result)

                    if (
                        qc_result.status == "fail"
                        and attempt < max_retries
                    ):
                        last_error = (
                            f"QC failed: {_qc_failure_summary(qc_result)}"
                        )
                        click.echo(
                            f"    \u26a0 {chunk_id}: QC fail, "
                            f"retry {attempt + 1}/{max_retries}"
                        )
                        continue
                    elif qc_result.status == "fail":
                        failed_chunks += 1
                        click.echo(
                            f"    \u2717 {chunk_id}: QC fail after "
                            f"{max_retries} retries"
                        )

                    chunk_paths.append(chunk_path)
                    success = True
                    break
                else:
                    last_error = result.error or "Unknown generation error"
                    if attempt < max_retries:
                        click.echo(
                            f"    \u26a0 {chunk_id}: attempt "
                            f"{attempt + 1} failed — {last_error}"
                        )
                    continue

            if not success:
                failed_chunks += 1
                click.echo(
                    f"    \u2717 {chunk_id}: FAILED — {last_error}"
                )
                qc_report.chunks.append(
                    _make_failure_result(
                        chunk_id, f"Generation failed: {last_error}"
                    )
                )

            chunk_index += 1

    # Stitch chunks with crossfade (using engine-specific crossfade)
    chapter_output = raw_dir / f"{ch_id}.wav"
    total_chunks = chunk_index

    if chunk_paths:
        stitch_ok = crossfade_stitch(
            chunk_paths,
            chapter_output,
            crossfade_ms=crossfade_ms,
            leading_silence_ms=leading_silence_ms,
        )
        if stitch_ok:
            click.echo(
                f"    \u2713 Stitched {len(chunk_paths)} chunks "
                f"\u2192 {ch_id}.wav (crossfade: {crossfade_ms}ms)"
            )
        else:
            click.echo(f"    \u2717 Stitch failed for {ch_id}")
    else:
        stitch_ok = False

    # ── VRAM management (XTTS on GPU) ──
    if hasattr(engine, "release_vram"):
        vram_strategy = gen_config.get(
            "xtts_vram_management", "empty_cache_per_chapter"
        )
        if vram_strategy == "conservative":
            engine.unload_model()
        elif vram_strategy == "reload_periodic":
            reload_n = int(gen_config.get("xtts_reload_every_n", 10))
            count = getattr(engine, "_generation_count", 0)
            if reload_n > 0 and count % reload_n == 0:
                engine.unload_model()
            else:
                engine.release_vram()
        else:
            # empty_cache_per_chapter (default)
            engine.release_vram()

    # Save QC report
    report_dir = project_path / "03_GENERATED"
    save_report(qc_report, report_dir)

    # Update pipeline status
    status = "complete" if stitch_ok and failed_chunks == 0 else "partial"
    update_chapter_status(
        project_id,
        ch_id,
        status,
        chunks=total_chunks,
        failed_chunks=failed_chunks,
        engine_used=engine_name,
        crossfade_ms=crossfade_ms,
        output=str(chapter_output) if stitch_ok else None,
    )

    return {
        "chapter_id": ch_id,
        "status": status,
        "total_chunks": total_chunks,
        "failed_chunks": failed_chunks,
        "engine_used": engine_name,
        "crossfade_ms": crossfade_ms,
        "output": str(chapter_output) if stitch_ok else None,
        "qc_fail_rate": qc_report.fail_rate,
    }


def _make_failure_result(chunk_id: str, error: str):
    """Create a failed ChunkQCResult."""
    from audioformation.qc.scanner import ChunkQCResult

    result = ChunkQCResult(chunk_id=chunk_id, file="")
    result.checks["generation"] = {"status": "fail", "message": error}
    return result


def _qc_failure_summary(qc_result) -> str:
    """Extract a brief summary of QC failures."""
    failures = []
    for check_name, check_data in qc_result.checks.items():
        if check_data.get("status") == "fail":
            failures.append(
                f"{check_name}: {check_data.get('message', '')}"
            )
    return "; ".join(failures) if failures else "Unknown QC failure"