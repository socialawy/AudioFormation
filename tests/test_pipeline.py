"""Tests for pipeline state machine, resumption, and gate logic."""

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

    def test_initial_status_is_pending(self, sample_project: str) -> None:
        status = get_node_status(sample_project, "bootstrap")
        assert status["status"] == "pending"

    def test_update_to_complete(self, sample_project: str) -> None:
        update_node_status(sample_project, "bootstrap", "complete")
        status = get_node_status(sample_project, "bootstrap")
        assert status["status"] == "complete"
        assert "timestamp" in status

    def test_update_with_extra_fields(self, sample_project: str) -> None:
        update_node_status(
            sample_project,
            "generate",
            "running",
            engine="edge",
        )
        status = get_node_status(sample_project, "generate")
        assert status["status"] == "running"
        assert status["engine"] == "edge"

    def test_invalid_node_raises(self, sample_project: str) -> None:
        with pytest.raises(ValueError, match="Unknown pipeline node"):
            update_node_status(sample_project, "fake_node", "complete")

    def test_invalid_status_raises(self, sample_project: str) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            update_node_status(sample_project, "bootstrap", "banana")

    def test_update_preserves_other_nodes(self, sample_project: str) -> None:
        update_node_status(sample_project, "bootstrap", "complete")
        update_node_status(sample_project, "ingest", "running")

        bs = get_node_status(sample_project, "bootstrap")
        ig = get_node_status(sample_project, "ingest")

        assert bs["status"] == "complete"
        assert ig["status"] == "running"


class TestChapterStatus:
    """Tests for chunk-level generation tracking."""

    def test_update_chapter_creates_chapters_dict(self, sample_project: str) -> None:
        update_chapter_status(
            sample_project, "ch01", "complete", chunks=18, duration_sec=142.3
        )

        status = get_node_status(sample_project, "generate")
        assert status["status"] == "partial"
        assert "chapters" in status
        assert status["chapters"]["ch01"]["status"] == "complete"
        assert status["chapters"]["ch01"]["chunks"] == 18

    def test_multiple_chapters_tracked(self, sample_project: str) -> None:
        update_chapter_status(sample_project, "ch01", "complete", chunks=18)
        update_chapter_status(sample_project, "ch02", "complete", chunks=24)
        update_chapter_status(
            sample_project,
            "ch03",
            "partial",
            chunks_done=14,
            chunks_total=23,
            error="CUDA out of memory",
        )

        status = get_node_status(sample_project, "generate")

        assert status["chapters"]["ch01"]["status"] == "complete"
        assert status["chapters"]["ch02"]["status"] == "complete"
        assert status["chapters"]["ch03"]["status"] == "partial"
        assert status["chapters"]["ch03"]["chunks_done"] == 14
        assert status["chapters"]["ch03"]["error"] == "CUDA out of memory"

    def test_get_incomplete_chapters(self, sample_project: str) -> None:
        update_chapter_status(sample_project, "ch01", "complete")
        update_chapter_status(sample_project, "ch02", "complete")
        update_chapter_status(sample_project, "ch03", "partial", chunks_done=5)
        update_chapter_status(sample_project, "ch04", "pending")

        incomplete = get_incomplete_chapters(sample_project)
        assert "ch03" in incomplete
        assert "ch04" in incomplete
        assert "ch01" not in incomplete
        assert "ch02" not in incomplete

    def test_get_incomplete_empty_when_all_done(self, sample_project: str) -> None:
        update_chapter_status(sample_project, "ch01", "complete")
        update_chapter_status(sample_project, "ch02", "complete")

        incomplete = get_incomplete_chapters(sample_project)
        assert incomplete == []


class TestResumePoint:
    """Tests for pipeline resumption logic."""

    def test_resumes_from_first_node(self, sample_project: str) -> None:
        point = get_resume_point(sample_project)
        assert point == "bootstrap"

    def test_resumes_after_completed_nodes(self, sample_project: str) -> None:
        update_node_status(sample_project, "bootstrap", "complete")
        update_node_status(sample_project, "ingest", "complete")

        point = get_resume_point(sample_project)
        assert point == "validate"

    def test_resumes_from_partial_node(self, sample_project: str) -> None:
        update_node_status(sample_project, "bootstrap", "complete")
        update_node_status(sample_project, "ingest", "complete")
        update_node_status(sample_project, "validate", "complete")
        update_node_status(sample_project, "generate", "partial")

        point = get_resume_point(sample_project)
        assert point == "generate"

    def test_explicit_from_node(self, sample_project: str) -> None:
        point = get_resume_point(sample_project, from_node="mix")
        assert point == "mix"

    def test_invalid_from_node_raises(self, sample_project: str) -> None:
        with pytest.raises(ValueError, match="Unknown node"):
            get_resume_point(sample_project, from_node="nonexistent")

    def test_skipped_nodes_are_skipped(self, sample_project: str) -> None:
        update_node_status(sample_project, "bootstrap", "complete")
        update_node_status(sample_project, "ingest", "complete")
        update_node_status(sample_project, "validate", "complete")
        update_node_status(sample_project, "generate", "complete")
        update_node_status(sample_project, "qc_scan", "complete")
        update_node_status(sample_project, "process", "complete")
        update_node_status(sample_project, "compose", "skipped")

        point = get_resume_point(sample_project)
        assert point == "mix"


class TestGates:
    """Tests for hard gate and auto gate logic."""

    def test_hard_gate_not_passed_initially(self, sample_project: str) -> None:
        assert is_gate_passed(sample_project, "validate") is False

    def test_hard_gate_passed_when_complete(self, sample_project: str) -> None:
        update_node_status(sample_project, "validate", "complete")
        assert is_gate_passed(sample_project, "validate") is True

    def test_non_gate_always_passes(self, sample_project: str) -> None:
        assert is_gate_passed(sample_project, "bootstrap") is True

    def test_cannot_proceed_past_failed_gate(self, sample_project: str) -> None:
        can, reason = can_proceed_to(sample_project, "generate")
        assert can is False
        assert "validate" in reason

    def test_can_proceed_after_gate_passes(self, sample_project: str) -> None:
        update_node_status(sample_project, "validate", "complete")
        can, reason = can_proceed_to(sample_project, "generate")
        assert can is True

    def test_cannot_proceed_to_export_without_qc_final(
        self, sample_project: str
    ) -> None:
        update_node_status(sample_project, "validate", "complete")
        # qc_final not passed
        can, reason = can_proceed_to(sample_project, "export")
        assert can is False
        assert "qc_final" in reason

    def test_can_proceed_to_export_with_all_gates(self, sample_project: str) -> None:
        update_node_status(sample_project, "validate", "complete")
        update_node_status(sample_project, "qc_final", "complete")
        can, reason = can_proceed_to(sample_project, "export")
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