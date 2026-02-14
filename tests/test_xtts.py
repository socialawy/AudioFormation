"""
Tests for XTTS v2 engine adapter.

All tests mock the TTS library — no GPU or model download required.
"""

import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

import numpy as np
import pytest
import soundfile as sf

from audioformation.engines.base import GenerationRequest, GenerationResult
from audioformation.engines.xtts import (
    XTTSEngine,
    _map_language,
    _get_duration,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def engine():
    """XTTSEngine with device forced to CPU (no real GPU needed)."""
    return XTTSEngine(device="cpu")


@pytest.fixture
def ref_audio(tmp_path):
    """Create a short reference WAV file."""
    ref = tmp_path / "reference.wav"
    sr = 24000
    duration = 6  # seconds
    samples = np.random.default_rng(42).uniform(-0.3, 0.3, sr * duration).astype(np.float32)
    sf.write(str(ref), samples, sr)
    return ref


@pytest.fixture
def mock_tts_model(tmp_path):
    """Mock TTS model that writes a real WAV file on tts_to_file."""

    def _fake_tts_to_file(text, file_path, speaker_wav, language, **kwargs):
        sr = 24000
        # ~1s of audio per 50 chars, minimum 0.5s
        duration = max(0.5, len(text) / 50.0)
        samples = np.random.default_rng(0).uniform(
            -0.3, 0.3, int(sr * duration)
        ).astype(np.float32)
        sf.write(file_path, samples, sr)

    model = MagicMock()
    model.tts_to_file = MagicMock(side_effect=_fake_tts_to_file)
    return model


# ── Properties ───────────────────────────────────────────


class TestProperties:
    def test_name(self, engine):
        assert engine.name == "xtts"

    def test_supports_cloning(self, engine):
        assert engine.supports_cloning is True

    def test_no_ssml(self, engine):
        assert engine.supports_ssml is False

    def test_gpu_not_required(self, engine):
        assert engine.requires_gpu is False


# ── Device detection ─────────────────────────────────────


class TestDeviceDetection:
    def test_explicit_cpu(self):
        e = XTTSEngine(device="cpu")
        assert e.device == "cpu"

    def test_explicit_gpu_maps_to_cuda(self):
        e = XTTSEngine(device="gpu")
        assert e.device == "cuda"

    def test_explicit_cuda(self):
        e = XTTSEngine(device="cuda")
        assert e.device == "cuda"

    def test_auto_detect_no_torch(self):
        """Without torch, falls back to CPU."""
        e = XTTSEngine(device=None)
        with patch.dict("sys.modules", {"torch": None}):
            # Force re-detection
            e._resolved_device = None
            # The import will fail → cpu
            assert e._detect_device() == "cpu"

    def test_auto_detect_cuda_available(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (4_000_000_000, 4_000_000_000)

        e = XTTSEngine(device=None)
        with patch.dict("sys.modules", {"torch": mock_torch}):
            with patch("audioformation.engines.xtts.logger"):
                result = e._detect_device()
        assert result == "cuda"

    def test_auto_detect_low_vram_falls_back(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        # Only 1 GB free
        mock_torch.cuda.mem_get_info.return_value = (1_000_000_000, 4_000_000_000)

        e = XTTSEngine(device=None)
        with patch.dict("sys.modules", {"torch": mock_torch}):
            with patch("audioformation.engines.xtts.logger"):
                result = e._detect_device()
        assert result == "cpu"


# ── Language mapping ─────────────────────────────────────


class TestLanguageMapping:
    @pytest.mark.parametrize(
        "input_lang, expected",
        [
            ("ar", "ar"),
            ("ar-SA", "ar"),
            ("ar-EG", "ar"),
            ("en", "en"),
            ("en-US", "en"),
            ("fr-FR", "fr"),
            ("de", "de"),
            ("zh-cn", "zh"),
        ],
    )
    def test_mapping(self, input_lang, expected):
        assert _map_language(input_lang) == expected


# ── Generation ───────────────────────────────────────────


class TestGeneration:
    def test_missing_reference_returns_error(self, engine, tmp_path):
        """XTTS must refuse generation without reference audio."""
        req = GenerationRequest(
            text="Hello",
            output_path=tmp_path / "out.wav",
            language="en",
            reference_audio=None,
        )
        result = asyncio.get_event_loop().run_until_complete(engine.generate(req))
        assert result.success is False
        assert "reference_audio" in result.error

    def test_nonexistent_reference_returns_error(self, engine, tmp_path):
        req = GenerationRequest(
            text="Hello",
            output_path=tmp_path / "out.wav",
            language="en",
            reference_audio=tmp_path / "does_not_exist.wav",
        )
        result = asyncio.get_event_loop().run_until_complete(engine.generate(req))
        assert result.success is False
        assert "not found" in result.error

    def test_successful_generation(self, engine, ref_audio, mock_tts_model, tmp_path):
        """Full generation with mocked TTS model."""
        engine._model = mock_tts_model
        out = tmp_path / "output.wav"

        req = GenerationRequest(
            text="مرحبا بالعالم هذا اختبار",
            output_path=out,
            language="ar",
            reference_audio=ref_audio,
        )
        result = asyncio.get_event_loop().run_until_complete(engine.generate(req))

        assert result.success is True
        assert result.output_path == out
        assert out.exists()
        assert out.stat().st_size > 0
        assert result.duration_sec > 0
        assert result.sample_rate == 24000

    def test_generation_passes_params(self, engine, ref_audio, mock_tts_model, tmp_path):
        """Temperature and repetition_penalty reach the model."""
        engine._model = mock_tts_model
        out = tmp_path / "output.wav"

        req = GenerationRequest(
            text="test",
            output_path=out,
            language="ar",
            reference_audio=ref_audio,
            params={"temperature": 0.3, "repetition_penalty": 8.0},
        )
        asyncio.get_event_loop().run_until_complete(engine.generate(req))

        call_kwargs = mock_tts_model.tts_to_file.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.3 or \
               call_kwargs[1].get("temperature") == 0.3

    def test_generation_increments_count(self, engine, ref_audio, mock_tts_model, tmp_path):
        engine._model = mock_tts_model
        assert engine._generation_count == 0

        for i in range(3):
            out = tmp_path / f"out_{i}.wav"
            req = GenerationRequest(
                text="chunk", output_path=out,
                language="en", reference_audio=ref_audio,
            )
            asyncio.get_event_loop().run_until_complete(engine.generate(req))

        assert engine._generation_count == 3

    def test_empty_output_returns_error(self, engine, ref_audio, tmp_path):
        """If model writes an empty file, report failure."""
        mock_model = MagicMock()
        mock_model.tts_to_file = MagicMock(
            side_effect=lambda **kw: Path(kw.get("file_path", kw.get("file_path"))).touch()
        )
        # The mock above creates an empty file
        engine._model = mock_model

        out = tmp_path / "out.wav"
        req = GenerationRequest(
            text="test", output_path=out,
            language="en", reference_audio=ref_audio,
        )

        # Need to handle the positional/keyword argument difference
        def _touch_file(text, file_path, speaker_wav, language, **kw):
            Path(file_path).touch()  # 0 bytes

        mock_model.tts_to_file = _touch_file
        result = asyncio.get_event_loop().run_until_complete(engine.generate(req))
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_cuda_oom_handled(self, engine, ref_audio, tmp_path):
        """CUDA OOM gets a specific error message."""
        mock_model = MagicMock()
        mock_model.tts_to_file = MagicMock(
            side_effect=RuntimeError("CUDA error: out of memory")
        )
        engine._model = mock_model

        req = GenerationRequest(
            text="test", output_path=tmp_path / "out.wav",
            language="ar", reference_audio=ref_audio,
        )

        with patch.object(engine, "release_vram"):
            result = asyncio.get_event_loop().run_until_complete(engine.generate(req))

        assert result.success is False
        assert "out of memory" in result.error.lower()

    def test_generic_exception_handled(self, engine, ref_audio, tmp_path):
        mock_model = MagicMock()
        mock_model.tts_to_file = MagicMock(
            side_effect=ValueError("something broke")
        )
        engine._model = mock_model

        req = GenerationRequest(
            text="test", output_path=tmp_path / "out.wav",
            language="en", reference_audio=ref_audio,
        )
        result = asyncio.get_event_loop().run_until_complete(engine.generate(req))
        assert result.success is False
        assert "ValueError" in result.error


# ── VRAM management ──────────────────────────────────────


class TestVRAMManagement:
    def test_release_vram_no_gpu(self, engine):
        """release_vram is a no-op when torch is absent."""
        with patch.dict("sys.modules", {"torch": None}):
            engine.release_vram()  # should not raise

    def test_release_vram_calls_empty_cache(self, engine):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.mem_get_info.return_value = (2_000_000_000, 4_000_000_000)

        with patch.dict("sys.modules", {"torch": mock_torch}):
            engine.release_vram()
        mock_torch.cuda.empty_cache.assert_called_once()

    def test_unload_model_clears_state(self, engine, mock_tts_model):
        engine._model = mock_tts_model
        engine._generation_count = 15
        engine._resolved_device = "cuda"

        with patch.dict("sys.modules", {"torch": MagicMock()}):
            engine.unload_model()

        assert engine._model is None
        assert engine._generation_count == 0
        assert engine._resolved_device is None

    def test_unload_model_noop_when_no_model(self, engine):
        """Unloading when nothing is loaded should not raise."""
        engine.unload_model()
        assert engine._model is None


# ── Voices / connection test ─────────────────────────────


class TestVoicesAndConnection:
    def test_list_voices_all(self, engine):
        voices = asyncio.get_event_loop().run_until_complete(
            engine.list_voices()
        )
        assert len(voices) == 17
        ids = [v["id"] for v in voices]
        assert "ar" in ids
        assert "en" in ids

    def test_list_voices_filtered(self, engine):
        voices = asyncio.get_event_loop().run_until_complete(
            engine.list_voices(language="ar")
        )
        assert len(voices) == 1
        assert voices[0]["id"] == "ar"

    def test_list_voices_no_match(self, engine):
        voices = asyncio.get_event_loop().run_until_complete(
            engine.list_voices(language="xx")
        )
        assert voices == []

    def test_connection_with_tts_importable(self, engine):
        with patch.dict("sys.modules", {"TTS": MagicMock(), "TTS.api": MagicMock()}):
            result = asyncio.get_event_loop().run_until_complete(
                engine.test_connection()
            )
        assert result is True

    def test_connection_without_tts(self, engine):
        """test_connection returns False when coqui-tts missing."""
        import importlib

        with patch("builtins.__import__", side_effect=ImportError("no TTS")):
            result = asyncio.get_event_loop().run_until_complete(
                engine.test_connection()
            )
        assert result is False


# ── Model loading ────────────────────────────────────────


class TestModelLoading:
    def test_ensure_model_raises_without_coqui(self, engine):
        with patch("builtins.__import__", side_effect=ImportError("no coqui")):
            with pytest.raises(RuntimeError, match="coqui-tts"):
                engine._ensure_model()

    def test_ensure_model_caches(self, engine, mock_tts_model):
        mock_tts_class = MagicMock(return_value=mock_tts_model)

        with patch(
            "audioformation.engines.xtts.XTTSEngine._ensure_model",
            side_effect=lambda: setattr(engine, "_model", mock_tts_model) or mock_tts_model,
        ):
            engine._model = mock_tts_model

        # Second call returns same instance
        model_a = engine._ensure_model()
        model_b = engine._ensure_model()
        assert model_a is model_b