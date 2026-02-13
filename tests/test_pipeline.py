"""Tests for pipeline state machine, resumption, and gate logic."""

import json
import pytest

from audioformation.pipeline import (
    PipelineError,
    get_node_status,
    update_node_status,
    update_chapter_status,
    get_resume_point,
    get_incomplete_chapters,
    is_gate_passed,
    can_proceed_to,
    nodes_in_range,
)
from audioformation.project import load_pipeline_status
from audioformation.config import PIPELINE_NODES


class TestNodeStatus:
    """Tests for reading and updating node status."""
    # ... (rest of the code remains the same)

    def test_initial_status_is_pending(self, sample_project) -> None:
        # bootstrap is "complete" in fixture, so check a node that's pending
        status = get_node_status(sample_project["id"], "ingest")
        assert status["status"] == "pending"

    def test_update_to_complete(self, sample_project) -> None:
        update_node_status(sample_project["id"], "bootstrap", "complete")
        status = get_node_status(sample_project["id"], "bootstrap")
        assert status["status"] == "complete"
        assert "timestamp" in status

    def test_update_with_extra_fields(self, sample_project) -> None:
        update_node_status(
            sample_project["id"],
            "generate",
            "running",
            engine="edge",
        )
        status = get_node_status(sample_project["id"], "generate")
        assert status["status"] == "running"
        assert status["engine"] == "edge"

    def test_invalid_node_raises(self, sample_project) -> None:
        with pytest.raises(ValueError, match="Unknown pipeline node"):
            update_node_status(sample_project["id"], "fake_node", "complete")

    def test_invalid_status_raises(self, sample_project) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            update_node_status(sample_project["id"], "bootstrap", "banana")

    def test_update_preserves_other_nodes(self, sample_project) -> None:
        update_node_status(sample_project["id"], "bootstrap", "complete")
        update_node_status(sample_project["id"], "ingest", "running")

        bs = get_node_status(sample_project["id"], "bootstrap")
        ig = get_node_status(sample_project["id"], "ingest")

        assert bs["status"] == "complete"
        assert ig["status"] == "running"


class TestChapterStatus:
    """Tests for chunk-level generation tracking."""

    def test_update_chapter_creates_chapters_dict(self, sample_project) -> None:
        update_chapter_status(
            sample_project["id"], "ch01", "complete", chunks=18, duration_sec=142.3
        )

        status = get_node_status(sample_project["id"], "generate")
        assert status["status"] == "partial"
        assert "chapters" in status
        assert status["chapters"]["ch01"]["status"] == "complete"
        assert status["chapters"]["ch01"]["chunks"] == 18

    def test_multiple_chapters_tracked(self, sample_project) -> None:
        update_chapter_status(sample_project["id"], "ch01", "complete", chunks=18)
        update_chapter_status(sample_project["id"], "ch02", "complete", chunks=24)
        update_chapter_status(
            sample_project["id"],
            "ch03",
            "partial",
            chunks_done=14,
            chunks_total=23,
            error="CUDA out of memory",
        )

        status = get_node_status(sample_project["id"], "generate")

        assert status["chapters"]["ch01"]["status"] == "complete"
        assert status["chapters"]["ch02"]["status"] == "complete"
        assert status["chapters"]["ch03"]["status"] == "partial"
        assert status["chapters"]["ch03"]["chunks_done"] == 14
        assert status["chapters"]["ch03"]["error"] == "CUDA out of memory"

    def test_get_incomplete_chapters(self, sample_project) -> None:
        update_chapter_status(sample_project["id"], "ch01", "complete")
        update_chapter_status(sample_project["id"], "ch02", "complete")
        update_chapter_status(sample_project["id"], "ch03", "partial", chunks_done=5)
        update_chapter_status(sample_project["id"], "ch04", "pending")

        incomplete = get_incomplete_chapters(sample_project["id"])
        assert "ch03" in incomplete
        assert "ch04" in incomplete
        assert "ch01" not in incomplete
        assert "ch02" not in incomplete

    def test_get_incomplete_empty_when_all_done(self, sample_project) -> None:
        update_chapter_status(sample_project["id"], "ch01", "complete")
        update_chapter_status(sample_project["id"], "ch02", "complete")

        incomplete = get_incomplete_chapters(sample_project["id"])
        assert incomplete == []


class TestResumePoint:
    """Tests for pipeline resumption logic."""

    def test_resumes_from_first_incomplete(self, sample_project) -> None:
        # bootstrap is complete in fixture, so resume should be ingest
        point = get_resume_point(sample_project["id"])
        assert point == "ingest"

    def test_resumes_after_completed_nodes(self, sample_project) -> None:
        update_node_status(sample_project["id"], "bootstrap", "complete")
        update_node_status(sample_project["id"], "ingest", "complete")

        point = get_resume_point(sample_project["id"])
        assert point == "validate"

    def test_resumes_from_partial_node(self, sample_project) -> None:
        update_node_status(sample_project["id"], "bootstrap", "complete")
        update_node_status(sample_project["id"], "ingest", "complete")
        update_node_status(sample_project["id"], "validate", "complete")
        update_node_status(sample_project["id"], "generate", "partial")

        point = get_resume_point(sample_project["id"])
        assert point == "generate"

    def test_explicit_from_node(self, sample_project) -> None:
        point = get_resume_point(sample_project["id"], from_node="mix")
        assert point == "mix"

    def test_invalid_from_node_raises(self, sample_project) -> None:
        with pytest.raises(ValueError, match="Unknown node"):
            get_resume_point(sample_project["id"], from_node="nonexistent")

    def test_skipped_nodes_are_skipped(self, sample_project) -> None:
        update_node_status(sample_project["id"], "bootstrap", "complete")
        update_node_status(sample_project["id"], "ingest", "complete")
        update_node_status(sample_project["id"], "validate", "complete")
        update_node_status(sample_project["id"], "generate", "complete")
        update_node_status(sample_project["id"], "qc_scan", "complete")
        update_node_status(sample_project["id"], "process", "complete")
        update_node_status(sample_project["id"], "compose", "skipped")

        point = get_resume_point(sample_project["id"])
        assert point == "mix"


class TestGates:
    """Tests for hard gate and auto gate logic."""

    def test_hard_gate_not_passed_initially(self, sample_project) -> None:
        assert is_gate_passed(sample_project["id"], "validate") is False

    def test_hard_gate_passed_when_complete(self, sample_project) -> None:
        update_node_status(sample_project["id"], "validate", "complete")
        assert is_gate_passed(sample_project["id"], "validate") is True

    def test_non_gate_always_passes(self, sample_project) -> None:
        assert is_gate_passed(sample_project["id"], "bootstrap") is True

    def test_cannot_proceed_past_failed_gate(self, sample_project) -> None:
        can, reason = can_proceed_to(sample_project["id"], "generate")
        assert can is False
        assert "validate" in reason

    def test_can_proceed_after_gate_passes(self, sample_project) -> None:
        update_node_status(sample_project["id"], "validate", "complete")
        can, reason = can_proceed_to(sample_project["id"], "generate")
        assert can is True

    def test_cannot_proceed_to_export_without_qc_final(self, sample_project) -> None:
        update_node_status(sample_project["id"], "validate", "complete")
        can, reason = can_proceed_to(sample_project["id"], "export")
        assert can is False
        assert "qc_final" in reason

    def test_can_proceed_to_export_with_all_gates(self, sample_project) -> None:
        update_node_status(sample_project["id"], "validate", "complete")
        update_node_status(sample_project["id"], "qc_final", "complete")
        can, reason = can_proceed_to(sample_project["id"], "export")
        assert can is True


class TestNodesInRange:
    """Tests for node range calculation."""

    def test_full_range(self) -> None:
        nodes = nodes_in_range("bootstrap")
        assert nodes == PIPELINE_NODES

    def test_from_generate(self) -> None:
        nodes = nodes_in_range("generate")
        assert nodes[0] == "generate"
        assert nodes[-1] == "export"
        assert "bootstrap" not in nodes

    def test_bounded_range(self) -> None:
        nodes = nodes_in_range("generate", "process")
        assert nodes == ["generate", "qc_scan", "process"]

    def test_single_node(self) -> None:
        nodes = nodes_in_range("mix", "mix")
        assert nodes == ["mix"]


class TestPipelineStatusWiring:
    """Verify every CLI-mapped node writes back to pipeline-status.json."""

    def test_mark_node_creates_status_file(self, tmp_path):
        """mark_node creates pipeline-status.json if missing."""
        from audioformation.pipeline import mark_node

        project_dir = tmp_path / "TEST"
        project_dir.mkdir()

        mark_node(project_dir, "bootstrap", "complete")

        status_file = project_dir / "pipeline-status.json"
        assert status_file.exists()

        data = json.loads(status_file.read_text())
        assert data["nodes"]["bootstrap"]["status"] == "complete"
        assert "timestamp" in data["nodes"]["bootstrap"]

    def test_mark_node_updates_existing(self, tmp_path):
        """mark_node updates existing status without clobbering other nodes."""
        from audioformation.pipeline import mark_node

        project_dir = tmp_path / "TEST"
        project_dir.mkdir()

        # Write two nodes
        mark_node(project_dir, "bootstrap", "complete")
        mark_node(project_dir, "ingest", "complete", files_ingested=3)

        data = json.loads((project_dir / "pipeline-status.json").read_text())
        assert data["nodes"]["bootstrap"]["status"] == "complete"
        assert data["nodes"]["ingest"]["status"] == "complete"
        assert data["nodes"]["ingest"]["files_ingested"] == 3

    def test_mark_node_overwrites_node(self, tmp_path):
        """Updating a node replaces its previous state."""
        from audioformation.pipeline import mark_node

        project_dir = tmp_path / "TEST"
        project_dir.mkdir()

        mark_node(project_dir, "generate", "partial", chunks_done=5)
        mark_node(project_dir, "generate", "complete", chunks_done=20)

        data = json.loads((project_dir / "pipeline-status.json").read_text())
        assert data["nodes"]["generate"]["status"] == "complete"
        assert data["nodes"]["generate"]["chunks_done"] == 20

    def test_get_node_status_missing_file(self, tmp_path):
        """mark_node + reading JSON works even with fresh directory."""
        from audioformation.pipeline import mark_node

        project_dir = tmp_path / "TEST"
        project_dir.mkdir()

        # No pipeline-status.json exists yet
        status_file = project_dir / "pipeline-status.json"
        assert not status_file.exists()

        # mark_node should create it
        mark_node(project_dir, "bootstrap", "complete")
        assert status_file.exists()

        data = json.loads(status_file.read_text(encoding="utf-8"))
        assert data["nodes"]["bootstrap"]["status"] == "complete"

    def test_get_node_status_missing_node(self, tmp_path):
        """Nodes not yet written default to absent in JSON."""
        from audioformation.pipeline import mark_node

        project_dir = tmp_path / "TEST"
        project_dir.mkdir()
        mark_node(project_dir, "bootstrap", "complete")

        data = json.loads(
            (project_dir / "pipeline-status.json").read_text(encoding="utf-8")
        )
        # "mix" was never written
        assert "mix" not in data["nodes"]

    def test_mark_node_extra_fields(self, tmp_path):
        """Extra kwargs are stored in node dict."""
        from audioformation.pipeline import mark_node

        project_dir = tmp_path / "TEST"
        project_dir.mkdir()

        mark_node(project_dir, "export", "complete",
                  formats=["mp3", "m4b"], checksum="abc123")

        data = json.loads((project_dir / "pipeline-status.json").read_text())
        assert data["nodes"]["export"]["formats"] == ["mp3", "m4b"]
        assert data["nodes"]["export"]["checksum"] == "abc123"