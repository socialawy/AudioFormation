"""
Hardware detection: GPU, VRAM, CUDA, ffmpeg.

Writes results to 00_CONFIG/hardware.json.
Used by engine selection and VRAM management strategy.
"""

import shutil
import subprocess
import json
from pathlib import Path
from typing import Any

from audioformation.config import VRAM_STRATEGY_THRESHOLDS


def detect_gpu() -> dict[str, Any]:
    """
    Detect GPU name, VRAM, and CUDA availability.

    Returns a dict suitable for hardware.json.
    """
    result: dict[str, Any] = {
        "gpu_available": False,
        "gpu_name": None,
        "vram_total_gb": None,
        "vram_free_gb": None,
        "cuda_available": False,
        "cuda_version": None,
        "recommended_vram_strategy": "cpu_only",
    }

    # Try PyTorch detection first
    try:
        import torch

        if torch.cuda.is_available():
            result["cuda_available"] = True
            result["cuda_version"] = torch.version.cuda
            result["gpu_available"] = True
            result["gpu_name"] = torch.cuda.get_device_name(0)

            vram_total = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            vram_free = (
                torch.cuda.get_device_properties(0).total_mem
                - torch.cuda.memory_reserved(0)
            ) / (1024**3)

            result["vram_total_gb"] = round(vram_total, 2)
            result["vram_free_gb"] = round(vram_free, 2)
            result["recommended_vram_strategy"] = _recommend_strategy(vram_total)

    except ImportError:
        # PyTorch not installed — try nvidia-smi fallback
        result.update(_detect_gpu_nvidia_smi())

    return result


def _detect_gpu_nvidia_smi() -> dict[str, Any]:
    """Fallback GPU detection via nvidia-smi CLI."""
    updates: dict[str, Any] = {}

    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if output.returncode == 0 and output.stdout.strip():
            parts = output.stdout.strip().split(",")
            if len(parts) >= 3:
                name = parts[0].strip()
                vram_total = float(parts[1].strip()) / 1024  # MiB → GiB
                vram_free = float(parts[2].strip()) / 1024

                updates["gpu_available"] = True
                updates["gpu_name"] = name
                updates["vram_total_gb"] = round(vram_total, 2)
                updates["vram_free_gb"] = round(vram_free, 2)
                updates["cuda_available"] = True
                updates["recommended_vram_strategy"] = _recommend_strategy(vram_total)

    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    return updates


def _recommend_strategy(vram_gb: float) -> str:
    """Recommend XTTS VRAM management strategy based on available VRAM."""
    if vram_gb < VRAM_STRATEGY_THRESHOLDS["conservative"]:
        return "conservative"
    elif vram_gb < VRAM_STRATEGY_THRESHOLDS["comfortable"]:
        return "empty_cache_per_chapter"
    else:
        return "empty_cache_per_chapter"


def detect_ffmpeg() -> dict[str, Any]:
    """Check if ffmpeg is available on PATH and get version."""
    result: dict[str, Any] = {
        "ffmpeg_available": False,
        "ffmpeg_path": None,
        "ffmpeg_version": None,
    }

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        result["ffmpeg_available"] = True
        result["ffmpeg_path"] = ffmpeg_path

        try:
            output = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if output.returncode == 0:
                # First line: "ffmpeg version X.Y.Z ..."
                first_line = output.stdout.split("\n")[0]
                result["ffmpeg_version"] = first_line.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return result


def detect_all() -> dict[str, Any]:
    """Run all hardware detection and return combined results."""
    gpu = detect_gpu()
    ffmpeg = detect_ffmpeg()

    return {
        **gpu,
        **ffmpeg,
    }


def write_hardware_json(project_path: Path) -> dict[str, Any]:
    """Detect hardware and write to project's 00_CONFIG/hardware.json."""
    hw = detect_all()
    hw_path = project_path / "00_CONFIG" / "hardware.json"
    hw_path.write_text(json.dumps(hw, indent=2, ensure_ascii=False))
    return hw