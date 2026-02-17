"""
Tests for multi-speaker chapter generation.

Verifies that [speaker_id] tags in chapter text correctly route
each segment to the right character → voice → engine.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from audioformation.utils.text import parse_chapter_segments, Segment


# ─────────────────────────────────────────────────────────
# Tag parsing tests (text.py integration)
# ─────────────────────────────────────────────────────────


class TestMultiSpeakerParsing:
    """Verify parse_chapter_segments in multi mode."""

    def test_single_narrator_no_tags(self):
        text = "Line one.\nLine two.\nLine three."
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 1
        assert segments[0].character == "narrator"
        assert "Line one." in segments[0].text

    def test_two_speakers(self):
        text = (
            "The narrator speaks.\n"
            "\n"
            "[hero] I will not give up.\n"
            "\n"
            "Back to narration."
        )
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 3
        assert segments[0].character == "narrator"
        assert segments[1].character == "hero"
        assert segments[2].character == "narrator"

    def test_three_speakers(self):
        text = (
            "Scene opens.\n"
            "\n"
            "[hero] My line.\n"
            "\n"
            "[villain] My response.\n"
            "\n"
            "Narrator closes."
        )
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 4
        chars = [s.character for s in segments]
        assert chars == ["narrator", "hero", "villain", "narrator"]

    def test_consecutive_same_speaker_merges(self):
        text = "[hero] First line.\n" "[hero] Second line."
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 1
        assert segments[0].character == "hero"
        assert "First line." in segments[0].text
        assert "Second line." in segments[0].text

    def test_blank_line_reverts_to_default(self):
        text = "[hero] Hero speaks.\n" "\n" "This should be narrator."
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 2
        assert segments[0].character == "hero"
        assert segments[1].character == "narrator"

    def test_inline_text_after_tag(self):
        text = "[hero] I refuse!"
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 1
        assert segments[0].character == "hero"
        assert "I refuse!" in segments[0].text

    def test_arabic_text_with_tags(self):
        text = (
            "قال الراوي بصوت هادئ.\n"
            "\n"
            "[hero] لن أستسلم أبداً.\n"
            "\n"
            "[villain] سنرى ذلك.\n"
            "\n"
            "عاد الصمت."
        )
        segments = parse_chapter_segments(
            text, mode="multi", default_character="narrator"
        )
        assert len(segments) == 4
        assert segments[0].character == "narrator"
        assert segments[1].character == "hero"
        assert "أستسلم" in segments[1].text
        assert segments[2].character == "villain"
        assert segments[3].character == "narrator"

    def test_single_mode_ignores_tags(self):
        text = "Narrator line.\n" "[hero] Hero line.\n" "More narration."
        segments = parse_chapter_segments(
            text, mode="single", default_character="narrator"
        )
        assert len(segments) == 1
        assert segments[0].character == "narrator"
        # Tag is stripped, but text after tag is preserved
        assert "Hero line." in segments[0].text


# ─────────────────────────────────────────────────────────
# Generation routing tests
# ─────────────────────────────────────────────────────────


@pytest.fixture
def multi_project(tmp_path):
    """
    Create a minimal project with multi-speaker chapter and two characters
    using different engines.
    """
    project_dir = tmp_path / "PROJECTS" / "MULTI_TEST"
    project_dir.mkdir(parents=True)

    # Create directory structure
    text_dir = project_dir / "01_TEXT" / "chapters"
    text_dir.mkdir(parents=True)
    raw_dir = project_dir / "03_GENERATED" / "raw"
    raw_dir.mkdir(parents=True)
    voices_dir = project_dir / "02_VOICES" / "references"
    voices_dir.mkdir(parents=True)

    # Create reference audio for hero
    ref_wav = voices_dir / "hero.wav"
    sf.write(
        str(ref_wav), [0.0] * 24000, 24000
    )  # Mocked sf.write works via conftest side_effect

    # Write chapter text with speaker tags
    chapter_text = (
        "The narrator begins.\n"
        "\n"
        "[hero] I am the hero.\n"
        "\n"
        "The narrator concludes."
    )
    (text_dir / "ch01.txt").write_text(chapter_text, encoding="utf-8")

    # Write project.json
    project_json = {
        "id": "MULTI_TEST",
        "version": "1.0",
        "languages": ["en"],
        "chapters": [
            {
                "id": "ch01",
                "title": "Test Chapter",
                "language": "en",
                "source": "01_TEXT/chapters/ch01.txt",
                "mode": "multi",
                "default_character": "narrator",
                "direction": {},
            }
        ],
        "characters": {
            "narrator": {
                "name": "Narrator",
                "engine": "edge",
                "voice": "en-US-GuyNeural",
                "reference_audio": None,
            },
            "hero": {
                "name": "Hero",
                "engine": "xtts",
                "voice": None,
                "reference_audio": "02_VOICES/references/hero.wav",
            },
        },
        "generation": {
            "chunk_max_chars": 200,
            "chunk_strategy": "sentence",
            "crossfade_ms": 120,
            "crossfade_overrides": {"edge": 120, "xtts": 80},
            "leading_silence_ms": 100,
            "max_retries_per_chunk": 1,
            "fail_threshold_percent": 50,
            "edge_tts_ssml": True,
            "xtts_temperature": 0.7,
            "xtts_repetition_penalty": 5.0,
            "xtts_vram_management": "empty_cache_per_chapter",
            "fallback_scope": "chapter",
            "fallback_chain": ["edge", "gtts"],
        },
        "qc": {
            "snr_min_db": 10,
            "max_duration_deviation_percent": 80,
            "clipping_threshold_dbfs": -0.5,
            "lufs_deviation_max": 10,
        },
        "mix": {"target_lufs": -16.0},
        "export": {"formats": ["mp3"]},
    }
    (project_dir / "project.json").write_text(
        json.dumps(project_json, indent=2), encoding="utf-8"
    )

    # Write pipeline-status.json
    (project_dir / "pipeline-status.json").write_text(
        json.dumps({"project_id": "MULTI_TEST", "nodes": {}}),
        encoding="utf-8",
    )

    return {
        "id": "MULTI_TEST",
        "dir": project_dir,
        "ref_wav": ref_wav,
    }


def _make_fake_engine(name, supports_ssml=False, supports_cloning=False):
    """Create a mock engine that writes real WAV files."""

    async def _generate(request):
        from audioformation.engines.base import GenerationResult

        sr = 24000
        dur = max(0.5, len(request.text) / 50.0)
        # Use mocked sf.write side effect from conftest or do simple touch
        Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(request.output_path).touch()

        return GenerationResult(
            success=True,
            output_path=request.output_path,
            duration_sec=dur,
            sample_rate=sr,
        )

    engine = MagicMock()
    engine.name = name
    engine.supports_ssml = supports_ssml
    engine.supports_cloning = supports_cloning
    engine.requires_gpu = False
    engine.generate = AsyncMock(side_effect=_generate)
    engine.release_vram = MagicMock()
    return engine


class TestMultiSpeakerGeneration:
    """
    Test that _generate_chapter routes segments to correct engines.
    """

    def test_multi_mode_uses_per_character_engine(self, multi_project, monkeypatch):
        """
        Narrator segments → edge engine
        Hero segments → xtts engine
        """

        async def _test():
            from audioformation.generate import _generate_chapter
            from audioformation.engines.registry import registry as real_registry

            edge_mock = _make_fake_engine("edge", supports_ssml=True)
            xtts_mock = _make_fake_engine("xtts", supports_cloning=True)

            # Patch registry to return our mocks
            original_get = real_registry.get

            def patched_get(name, **kwargs):
                if name == "edge":
                    return edge_mock
                if name == "xtts":
                    return xtts_mock
                return original_get(name, **kwargs)

            monkeypatch.setattr(real_registry, "get", patched_get)

            # Patch project functions
            proj = multi_project
            pj = json.loads((proj["dir"] / "project.json").read_text())

            monkeypatch.setattr(
                "audioformation.generate.get_project_path",
                lambda pid: proj["dir"],
            )

            result = await _generate_chapter(
                project_id=proj["id"],
                project_path=proj["dir"],
                chapter=pj["chapters"][0],
                characters=pj["characters"],
                gen_config=pj["generation"],
                qc_config=pj["qc"],
                target_lufs=-16.0,
                raw_dir=proj["dir"] / "03_GENERATED" / "raw",
                engine_override=None,
            )

            assert result["status"] in ("complete", "partial")
            assert result["total_chunks"] > 0

            # Verify both engines were called
            assert (
                edge_mock.generate.call_count > 0
            ), "Edge should handle narrator segments"
            assert xtts_mock.generate.call_count > 0, "XTTS should handle hero segments"

            # Verify edge got narrator text, xtts got hero text
            edge_texts = [
                call.args[0].text
                if call.args
                else call.kwargs.get("request", call[0][0]).text
                for call in edge_mock.generate.call_args_list
            ]
            xtts_texts = [
                call.args[0].text
                if call.args
                else call.kwargs.get("request", call[0][0]).text
                for call in xtts_mock.generate.call_args_list
            ]

            assert any(
                "narrator" in t.lower() for t in edge_texts
            ), f"Edge should get narrator text, got: {edge_texts}"
            assert any(
                "hero" in t.lower() for t in xtts_texts
            ), f"XTTS should get hero text, got: {xtts_texts}"

        asyncio.run(_test())

    def test_engine_override_forces_all_segments(self, multi_project, monkeypatch):
        """When --engine flag is set, ALL segments use that engine."""

        async def _test():
            from audioformation.generate import _generate_chapter
            from audioformation.engines.registry import registry as real_registry

            edge_mock = _make_fake_engine("edge", supports_ssml=True)
            xtts_mock = _make_fake_engine("xtts", supports_cloning=True)

            original_get = real_registry.get

            def patched_get(name, **kwargs):
                if name == "edge":
                    return edge_mock
                if name == "xtts":
                    return xtts_mock
                return original_get(name, **kwargs)

            monkeypatch.setattr(real_registry, "get", patched_get)

            proj = multi_project
            pj = json.loads((proj["dir"] / "project.json").read_text())

            monkeypatch.setattr(
                "audioformation.generate.get_project_path",
                lambda pid: proj["dir"],
            )

            result = await _generate_chapter(
                project_id=proj["id"],
                project_path=proj["dir"],
                chapter=pj["chapters"][0],
                characters=pj["characters"],
                gen_config=pj["generation"],
                qc_config=pj["qc"],
                target_lufs=-16.0,
                raw_dir=proj["dir"] / "03_GENERATED" / "raw",
                engine_override="edge",  # force all to edge
            )

            assert result["total_chunks"] > 0
            # Only edge should be called — override trumps character config
            assert edge_mock.generate.call_count > 0
            assert xtts_mock.generate.call_count == 0

        asyncio.run(_test())

    def test_xtts_vram_released_after_multi_chapter(self, multi_project, monkeypatch):
        """XTTS release_vram is called when XTTS was used in a chapter."""

        async def _test():
            from audioformation.generate import _generate_chapter
            from audioformation.engines.registry import registry as real_registry

            edge_mock = _make_fake_engine("edge", supports_ssml=True)
            xtts_mock = _make_fake_engine("xtts", supports_cloning=True)

            original_get = real_registry.get

            def patched_get(name, **kwargs):
                if name == "edge":
                    return edge_mock
                if name == "xtts":
                    return xtts_mock
                return original_get(name, **kwargs)

            monkeypatch.setattr(real_registry, "get", patched_get)

            proj = multi_project
            pj = json.loads((proj["dir"] / "project.json").read_text())

            monkeypatch.setattr(
                "audioformation.generate.get_project_path",
                lambda pid: proj["dir"],
            )

            await _generate_chapter(
                project_id=proj["id"],
                project_path=proj["dir"],
                chapter=pj["chapters"][0],
                characters=pj["characters"],
                gen_config=pj["generation"],
                qc_config=pj["qc"],
                target_lufs=-16.0,
                raw_dir=proj["dir"] / "03_GENERATED" / "raw",
                engine_override=None,
            )

            # XTTS was used → release_vram should have been called
            xtts_mock.release_vram.assert_called()

        asyncio.run(_test())

    def test_single_mode_unchanged(self, multi_project, monkeypatch):
        """Single mode still works — all segments use chapter character."""

        async def _test():
            from audioformation.generate import _generate_chapter
            from audioformation.engines.registry import registry as real_registry

            edge_mock = _make_fake_engine("edge", supports_ssml=True)
            xtts_mock = _make_fake_engine("xtts", supports_cloning=True)

            original_get = real_registry.get

            def patched_get(name, **kwargs):
                if name == "edge":
                    return edge_mock
                if name == "xtts":
                    return xtts_mock
                return original_get(name, **kwargs)

            monkeypatch.setattr(real_registry, "get", patched_get)

            proj = multi_project
            pj = json.loads((proj["dir"] / "project.json").read_text())

            # Change chapter to single mode with narrator
            chapter = pj["chapters"][0].copy()
            chapter["mode"] = "single"
            chapter["character"] = "narrator"

            monkeypatch.setattr(
                "audioformation.generate.get_project_path",
                lambda pid: proj["dir"],
            )

            result = await _generate_chapter(
                project_id=proj["id"],
                project_path=proj["dir"],
                chapter=chapter,
                characters=pj["characters"],
                gen_config=pj["generation"],
                qc_config=pj["qc"],
                target_lufs=-16.0,
                raw_dir=proj["dir"] / "03_GENERATED" / "raw",
                engine_override=None,
            )

            assert result["total_chunks"] > 0
            # Only edge (narrator's engine) should be called
            assert edge_mock.generate.call_count > 0
            assert xtts_mock.generate.call_count == 0

        asyncio.run(_test())


class TestMultiSpeakerEdgeCases:
    def test_unknown_character_falls_back(self, multi_project, monkeypatch):
        """Segment with unknown character falls back to chapter defaults."""

        async def _test():
            from audioformation.generate import _generate_chapter
            from audioformation.engines.registry import registry as real_registry

            edge_mock = _make_fake_engine("edge", supports_ssml=True)

            original_get = real_registry.get

            def patched_get(name, **kwargs):
                if name == "edge":
                    return edge_mock
                return original_get(name, **kwargs)

            monkeypatch.setattr(real_registry, "get", patched_get)

            proj = multi_project
            pj = json.loads((proj["dir"] / "project.json").read_text())

            # Write chapter with unknown speaker tag
            chapter_text = (
                "Narrator line.\n"
                "\n"
                "[unknown_character] Mystery line.\n"
                "\n"
                "Back to narrator."
            )
            text_path = proj["dir"] / "01_TEXT" / "chapters" / "ch01.txt"
            text_path.write_text(chapter_text, encoding="utf-8")

            monkeypatch.setattr(
                "audioformation.generate.get_project_path",
                lambda pid: proj["dir"],
            )

            # Should not crash — unknown character gets empty char_data → default engine
            result = await _generate_chapter(
                project_id=proj["id"],
                project_path=proj["dir"],
                chapter=pj["chapters"][0],
                characters=pj["characters"],
                gen_config=pj["generation"],
                qc_config=pj["qc"],
                target_lufs=-16.0,
                raw_dir=proj["dir"] / "03_GENERATED" / "raw",
                engine_override=None,
            )

            assert result["total_chunks"] > 0
            assert result["status"] in ("complete", "partial")

        asyncio.run(_test())
