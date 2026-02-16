"""
Pipeline state machine — node execution, resumption, status tracking.

Tracks state at chunk level for the Generate node, node level for all others.
Supports `--from <node>` resumption by checking pipeline-status.json.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audioformation.config import PIPELINE_NODES, HARD_GATES, AUTO_GATES
from audioformation.project import (
    load_pipeline_status,
    save_pipeline_status,
)

# Configure pipeline logging
pipeline_logger = logging.getLogger("audioformation.pipeline")

class PipelineError(Exception):
    """Raised when a pipeline gate fails."""


def get_node_status(project_id: str, node: str) -> dict[str, Any]:
    """Get the status dict for a specific pipeline node."""
    status = load_pipeline_status(project_id)
    return status.get("nodes", {}).get(node, {"status": "pending"})


def update_node_status(
    project_id: str,
    node: str,
    status: str,
    **extra: Any,
) -> None:
    """
    Update a pipeline node's status.

    Args:
        project_id: Project identifier.
        node: Pipeline node name (must be in PIPELINE_NODES).
        status: One of 'pending', 'running', 'complete', 'partial', 'failed', 'skipped'.
        **extra: Additional fields to store (e.g., chapters, error, timestamp).
    """
    if node not in PIPELINE_NODES:
        raise ValueError(f"Unknown pipeline node: {node}")

    valid_statuses = {"pending", "running", "complete", "partial", "failed", "skipped"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

    pipeline = load_pipeline_status(project_id)
    node_data = pipeline["nodes"].get(node, {})
    old_status = node_data.get("status", "pending")
    node_data["status"] = status
    node_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    node_data.update(extra)
    pipeline["nodes"][node] = node_data
    save_pipeline_status(project_id, pipeline)
    
    # Enhanced logging
    log_msg = f"Node {node} status: {old_status} → {status}"
    if extra:
        log_msg += f" (extra: {extra})"
    pipeline_logger.info(f"[{project_id}] {log_msg}")
    
    if status == "failed":
        pipeline_logger.error(f"[{project_id}] Node {node} failed: {extra.get('error', 'Unknown error')}")
    elif status == "complete":
        pipeline_logger.info(f"[{project_id}] Node {node} completed successfully")


def update_chapter_status(
    project_id: str,
    chapter_id: str,
    status: str,
    **extra: Any,
) -> None:
    """
    Update generation status for a specific chapter (chunk-level tracking).

    This provides fine-grained resumability within the Generate node.
    """
    pipeline = load_pipeline_status(project_id)
    gen_node = pipeline["nodes"].get("generate", {"status": "running"})

    if "chapters" not in gen_node:
        gen_node["chapters"] = {}

    gen_node["chapters"][chapter_id] = {"status": status, **extra}
    gen_node["status"] = "partial"
    gen_node["timestamp"] = datetime.now(timezone.utc).isoformat()

    pipeline["nodes"]["generate"] = gen_node
    save_pipeline_status(project_id, pipeline)


def get_resume_point(project_id: str, from_node: str | None = None) -> str:
    """
    Determine which node to resume from.

    If from_node is specified, validates it and returns it.
    Otherwise, finds the first non-complete node.
    """
    if from_node:
        if from_node not in PIPELINE_NODES:
            raise ValueError(
                f"Unknown node '{from_node}'. Valid: {', '.join(PIPELINE_NODES)}"
            )
        return from_node

    status = load_pipeline_status(project_id)
    nodes = status.get("nodes", {})

    for node in PIPELINE_NODES:
        node_status = nodes.get(node, {}).get("status", "pending")
        if node_status not in ("complete", "skipped"):
            return node

    return PIPELINE_NODES[-1]  # All complete — return last node


def get_incomplete_chapters(project_id: str) -> list[str]:
    """
    Get list of chapter IDs that need (re-)generation.

    Returns chapters with status != 'complete' in the generate node.
    """
    status = load_pipeline_status(project_id)
    gen_node = status.get("nodes", {}).get("generate", {})
    chapters = gen_node.get("chapters", {})

    incomplete = []
    for ch_id, ch_data in chapters.items():
        if ch_data.get("status") != "complete":
            incomplete.append(ch_id)

    return incomplete


def is_gate_passed(project_id: str, node: str) -> bool:
    """Check whether a gate node has been passed (status == complete)."""
    if node not in HARD_GATES and node not in AUTO_GATES:
        return True  # Not a gate node
    node_data = get_node_status(project_id, node)
    return node_data.get("status") == "complete"


def can_proceed_to(project_id: str, target_node: str) -> tuple[bool, str]:
    """
    Check if the pipeline can proceed to target_node.

    Returns (can_proceed, reason).
    All preceding hard gates must be passed.
    """
    target_idx = PIPELINE_NODES.index(target_node)

    for i in range(target_idx):
        node = PIPELINE_NODES[i]
        if node in HARD_GATES and not is_gate_passed(project_id, node):
            return False, f"Hard gate '{node}' has not passed."

    return True, "OK"


def nodes_in_range(from_node: str, to_node: str | None = None) -> list[str]:
    """
    Get the ordered list of nodes from from_node to to_node (inclusive).

    If to_node is None, goes to the end of the pipeline.
    """
    start = PIPELINE_NODES.index(from_node)
    if to_node:
        end = PIPELINE_NODES.index(to_node) + 1
    else:
        end = len(PIPELINE_NODES)

    return PIPELINE_NODES[start:end]


def mark_node(project_dir: Path, node: str, status: str, **extra):
    """
    Convenience wrapper: update a pipeline node's status.
    
    Args:
        project_dir: Path to project root
        node: Node name (bootstrap, ingest, validate, etc.)
        status: One of: pending, complete, partial, failed, skipped
        **extra: Additional fields merged into node dict
    """
    status_file = project_dir / "pipeline-status.json"

    if status_file.exists():
        data = json.loads(status_file.read_text(encoding="utf-8"))
    else:
        data = {"project_id": project_dir.name, "nodes": {}}

    node_data = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    node_data.update(extra)

    data.setdefault("nodes", {})[node] = node_data

    status_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )