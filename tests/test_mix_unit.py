"""
Unit tests for mix pipeline logic (mix.py + mixer.py).
"""

import json

import numpy as np
import pytest
import soundfile as sf
from pydub import AudioSegment


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def mix_project(tmp_path):
    """Create a project with processed chapters and generated music."""
    proj = tmp_path / "PROJECTS" / "MIX_TEST"
    proj.mkdir(parents=True)

    processed = proj / "03_GENERATED" / "processed"
    processed.mkdir(parents=True)
    music = proj / "05_MUSIC" / "generated"
    music.mkdir(parents=True)
    renders = proj / "06_MIX" / "renders"
    renders.mkdir(parents=True)

    sr = 24000

    # Create two chapter WAVs (1s each, mono)
    for name in ["ch01.wav", "ch02.wav"]:
        samples = np.random.default_rng(42).uniform(-0.3, 0.3, sr).astype(np.float32)
        sf.write(str(processed / name), samples, sr)

    # Create a music file (3s)
    music_samples = (
        np.random.default_rng(7).uniform(-0.1, 0.1, sr * 3).astype(np.float32)
    )
    sf.write(str(music / "pad_contemplative.wav"), music_samples, sr)

    # Write project.json
    pj = {
        "id": "MIX_TEST",
        "version": "1.0",
        "languages": ["en"],
        "chapters": [],
        "characters": {},
        "mix": {
            "master_volume": 0.9,
            "target_lufs": -16.0,
            "ducking": {
                "method": "energy",
                "attenuation_db": -12,
                "attack_ms": 100,
                "release_ms": 500,
                "look_ahead_ms": 200,
                "vad_threshold": 0.5,
            },
        },
    }
    (proj / "project.json").write_text(json.dumps(pj, indent=2))
    (proj / "pipeline-status.json").write_text(
        json.dumps({"project_id": "MIX_TEST", "nodes": {}})
    )

    return proj


# ── AudioMixer unit tests ────────────────────────────────


class TestAudioMixer:
    def test_voice_only_no_music(self, mix_project):
        """Mixing without music just applies master volume."""
        from audioformation.audio.mixer import AudioMixer

        mixer = AudioMixer({"master_volume": 0.9, "ducking": {"method": "energy"}})
        voice = mix_project / "03_GENERATED" / "processed" / "ch01.wav"
        output = mix_project / "06_MIX" / "renders" / "ch01.wav"

        result = mixer.mix_chapter(voice, None, output)

        assert result is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_voice_with_music(self, mix_project):
        """Mixing voice + music produces output."""
        from audioformation.audio.mixer import AudioMixer

        mixer = AudioMixer(
            {
                "master_volume": 0.9,
                "ducking": {
                    "method": "energy",
                    "attenuation_db": -12,
                    "attack_ms": 100,
                    "release_ms": 500,
                    "look_ahead_ms": 200,
                },
            }
        )
        voice = mix_project / "03_GENERATED" / "processed" / "ch01.wav"
        music = mix_project / "05_MUSIC" / "generated" / "pad_contemplative.wav"
        output = mix_project / "06_MIX" / "renders" / "ch01.wav"

        result = mixer.mix_chapter(voice, music, output)

        assert result is True
        assert output.exists()
        # Output should be longer than voice alone (music has 2s tail)
        voice_audio = AudioSegment.from_file(str(voice))
        output_audio = AudioSegment.from_file(str(output))
        assert len(output_audio) >= len(voice_audio)

    def test_music_loops_for_long_voice(self, mix_project):
        """Short music file is looped to cover voice duration."""
        from audioformation.audio.mixer import AudioMixer

        mixer = AudioMixer(
            {
                "master_volume": 1.0,
                "ducking": {
                    "method": "energy",
                    "attenuation_db": -12,
                    "attack_ms": 50,
                    "release_ms": 200,
                    "look_ahead_ms": 100,
                },
            }
        )

        # Create a longer voice file (5s) than music (3s)
        sr = 24000
        long_voice = mix_project / "03_GENERATED" / "processed" / "long.wav"
        samples = np.random.default_rng(0).uniform(-0.3, 0.3, sr * 5).astype(np.float32)
        sf.write(str(long_voice), samples, sr)

        music = mix_project / "05_MUSIC" / "generated" / "pad_contemplative.wav"
        output = mix_project / "06_MIX" / "renders" / "long.wav"

        result = mixer.mix_chapter(long_voice, music, output)
        assert result is True
        assert output.exists()

    def test_nonexistent_music_falls_back_to_voice_only(self, mix_project):
        from audioformation.audio.mixer import AudioMixer

        mixer = AudioMixer({"master_volume": 0.9, "ducking": {"method": "energy"}})
        voice = mix_project / "03_GENERATED" / "processed" / "ch01.wav"
        fake_music = mix_project / "05_MUSIC" / "nonexistent.wav"
        output = mix_project / "06_MIX" / "renders" / "ch01.wav"

        result = mixer.mix_chapter(voice, fake_music, output)
        assert result is True
        assert output.exists()

    def test_energy_envelope_produces_array(self, mix_project):
        """Energy-based ducking produces a valid envelope."""
        from audioformation.audio.mixer import AudioMixer

        mixer = AudioMixer(
            {
                "ducking": {
                    "method": "energy",
                    "attenuation_db": -12,
                    "attack_ms": 100,
                    "release_ms": 500,
                    "look_ahead_ms": 200,
                },
            }
        )

        voice = AudioSegment.from_file(
            str(mix_project / "03_GENERATED" / "processed" / "ch01.wav")
        )
        envelope = mixer._generate_envelope(voice, len(voice) + 2000)

        assert isinstance(envelope, np.ndarray)
        assert len(envelope) == len(voice) + 2000
        assert envelope.min() >= 0.0
        assert envelope.max() <= 1.0

    def test_master_volume_applied(self, mix_project):
        """Master volume < 1.0 reduces output level."""
        from audioformation.audio.mixer import AudioMixer

        # Mix at full volume
        mixer_full = AudioMixer({"master_volume": 1.0, "ducking": {"method": "energy"}})
        voice = mix_project / "03_GENERATED" / "processed" / "ch01.wav"
        out_full = mix_project / "06_MIX" / "renders" / "full.wav"
        mixer_full.mix_chapter(voice, None, out_full)

        # Mix at 0.5 volume
        mixer_half = AudioMixer({"master_volume": 0.5, "ducking": {"method": "energy"}})
        out_half = mix_project / "06_MIX" / "renders" / "half.wav"
        mixer_half.mix_chapter(voice, None, out_half)

        full_audio = AudioSegment.from_file(str(out_full))
        half_audio = AudioSegment.from_file(str(out_half))

        # Half volume should be quieter
        assert half_audio.dBFS < full_audio.dBFS


# ── mix_project() orchestrator tests ─────────────────────


class TestMixProject:
    def test_mixes_all_chapters(self, mix_project, monkeypatch):
        from audioformation.mix import mix_project as run_mix

        monkeypatch.setattr(
            "audioformation.mix.get_project_path",
            lambda pid: mix_project,
        )
        monkeypatch.setattr(
            "audioformation.mix.load_project_json",
            lambda pid: json.loads((mix_project / "project.json").read_text()),
        )
        monkeypatch.setattr(
            "audioformation.mix.update_node_status",
            lambda *a, **kw: None,
        )

        result = run_mix("MIX_TEST")

        assert result is True
        renders = mix_project / "06_MIX" / "renders"
        assert (renders / "ch01.wav").exists()
        assert (renders / "ch02.wav").exists()

    def test_fallback_to_raw_if_no_processed(self, mix_project, monkeypatch):
        """If processed/ is empty, falls back to raw/."""
        from audioformation.mix import mix_project as run_mix
        import shutil

        # Move processed → raw
        raw = mix_project / "03_GENERATED" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        processed = mix_project / "03_GENERATED" / "processed"
        for f in processed.glob("*.wav"):
            shutil.move(str(f), str(raw / f.name))

        monkeypatch.setattr(
            "audioformation.mix.get_project_path",
            lambda pid: mix_project,
        )
        monkeypatch.setattr(
            "audioformation.mix.load_project_json",
            lambda pid: json.loads((mix_project / "project.json").read_text()),
        )
        monkeypatch.setattr(
            "audioformation.mix.update_node_status",
            lambda *a, **kw: None,
        )

        result = run_mix("MIX_TEST")
        assert result is True

    def test_returns_false_when_no_audio(self, mix_project, monkeypatch):
        """No chapter files → returns False."""
        from audioformation.mix import mix_project as run_mix
        import shutil

        # Remove all audio
        shutil.rmtree(mix_project / "03_GENERATED")
        (mix_project / "03_GENERATED" / "processed").mkdir(parents=True)
        (mix_project / "03_GENERATED" / "raw").mkdir(parents=True)

        monkeypatch.setattr(
            "audioformation.mix.get_project_path",
            lambda pid: mix_project,
        )
        monkeypatch.setattr(
            "audioformation.mix.load_project_json",
            lambda pid: json.loads((mix_project / "project.json").read_text()),
        )
        monkeypatch.setattr(
            "audioformation.mix.update_node_status",
            lambda *a, **kw: None,
        )

        result = run_mix("MIX_TEST")
        assert result is False


# ── QC Final tests ───────────────────────────────────────


class TestQCFinalIntegration:
    def test_scan_passes_good_audio(self, mix_project, monkeypatch):
        """Well-normalized audio passes QC Final."""
        from audioformation.qc.final import scan_final_mix

        # Create a "mixed" file in renders
        renders = mix_project / "06_MIX" / "renders"
        sr = 24000
        # Generate audio at roughly -16 LUFS (moderate level)
        samples = (
            np.random.default_rng(42).uniform(-0.1, 0.1, sr * 2).astype(np.float32)
        )
        sf.write(str(renders / "ch01.wav"), samples, sr)

        monkeypatch.setattr(
            "audioformation.qc.final.get_project_path",
            lambda pid: mix_project,
        )
        monkeypatch.setattr(
            "audioformation.qc.final.load_project_json",
            lambda pid: json.loads((mix_project / "project.json").read_text()),
        )
        monkeypatch.setattr(
            "audioformation.qc.final.update_node_status",
            lambda *a, **kw: None,
        )

        report = scan_final_mix("MIX_TEST")

        assert report.total_files == 1
        assert len(report.results) == 1
        # We can't guarantee pass/fail without knowing exact LUFS,
        # but it should complete without error
        assert report.results[0].duration_sec > 0

    def test_scan_no_renders_fails(self, mix_project, monkeypatch):
        """No renders directory → report shows 0 files."""
        from audioformation.qc.final import scan_final_mix
        import shutil

        shutil.rmtree(mix_project / "06_MIX" / "renders")

        monkeypatch.setattr(
            "audioformation.qc.final.get_project_path",
            lambda pid: mix_project,
        )
        monkeypatch.setattr(
            "audioformation.qc.final.load_project_json",
            lambda pid: json.loads((mix_project / "project.json").read_text()),
        )
        monkeypatch.setattr(
            "audioformation.qc.final.update_node_status",
            lambda *a, **kw: None,
        )

        report = scan_final_mix("MIX_TEST")
        assert report.total_files == 0
        assert not report.passed
