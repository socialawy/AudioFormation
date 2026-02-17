#!/usr/bin/env python3
"""
E2E CLI Test Suite for Audio-Formation Pipeline
Tests all 4 TTS engines across full pipeline with detailed logging.
Uses shell=False for subprocess to ensure Windows compatibility.
"""

import json
import os
import sys
import time
import pytest
import subprocess
from pathlib import Path
from datetime import datetime

# Add tools directory to path for e2e_logger
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

try:
    from e2e_logger import E2ELogger

    E2E_LOGGER_AVAILABLE = True
except ImportError:
    E2E_LOGGER_AVAILABLE = False

# Configuration
TEST_SAMPLES_DIR = (Path(__file__).parent.parent / "test_samples").resolve()
ENGINES = ["edge", "gtts", "xtts", "elevenlabs"]
VOICES = {
    "edge": "ar-EG-SalmaNeural",
    "gtts": "ar",  # gTTS uses language codes
    "xtts": None,  # XTTS uses speaker embedding
    "elevenlabs": None,  # ElevenLabs uses pre-trained voices
}

EXPORT_FORMATS = ["mp3", "m4b", "wav"]


@pytest.fixture(scope="session", autouse=True)
def setup_test_data():
    """Ensure test samples directory and files exist before running tests."""
    TEST_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "contemplative.txt": "This is a quiet, contemplative scene. The wind whispers through the ancient trees.",
        "energetic.txt": "Action! Movement! The chase was on, running fast through the crowded streets!",
    }

    for name, content in files.items():
        p = TEST_SAMPLES_DIR / name
        if not p.exists():
            p.write_text(content, encoding="utf-8")


@pytest.mark.skipif(
    not E2E_LOGGER_AVAILABLE, reason="E2E logger utilities not available"
)
class TestE2EPipeline:
    """E2E tests for the complete audio pipeline"""

    @pytest.fixture(scope="class")
    def logger(self):
        """Create E2E logger for test documentation"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger = E2ELogger(f"E2E_TEST_RESULTS_{timestamp}.md")
        logger.log_section("E2E Pipeline Test Suite")
        # Add test_results attribute to fix AttributeError
        logger.test_results = {}
        yield logger
        logger.save()

    def test_verify_test_data(self, logger):
        """Verify test data files exist"""
        logger.log_section("Test Data Verification")

        assert (
            TEST_SAMPLES_DIR.exists()
        ), f"Test samples directory not found: {TEST_SAMPLES_DIR}"

        required_files = ["contemplative.txt", "energetic.txt"]
        for filename in required_files:
            filepath = TEST_SAMPLES_DIR / filename
            assert filepath.exists(), f"Required test file missing: {filename}"

            file_info = logger.log_file_info(filepath)
            logger.entries.append(
                f"- {filename}: {file_info['size_mb']} MB, {file_info['sha256_prefix']}\n"
            )

        logger.entries.append("✅ All test data verified\n")

    @pytest.mark.parametrize("engine", ["edge", "gtts", "xtts"])
    def test_engine_pipeline(self, logger, engine):
        """Test complete pipeline for a specific engine"""
        if not self._check_engine_available(engine):
            logger.log_skip(f"{engine} not available on this system")
            pytest.skip(f"{engine} not available")

        project_name = f"E2E_TEST_{engine.upper()}_{int(time.time())}"
        logger.start_engine_section(engine)

        try:
            success, error_msg = self._run_engine_test(logger, engine, project_name)
            if not success:
                logger.log_error(f"Pipeline failed: {error_msg}")

            assert success, f"Pipeline test failed for {engine}: {error_msg}"

            logger.test_results[engine] = {
                "project": project_name,
                "status": "PASS",
            }

        except Exception as e:
            logger.log_error(f"Exception in {engine} test", e)
            logger.test_results[engine] = {
                "status": "FAIL",
                "error": str(e),
            }
            raise

    @pytest.mark.skipif(
        not os.environ.get("ELEVENLABS_API_KEY"),
        reason="ElevenLabs API key not configured",
    )
    def test_elevenlabs_pipeline(self, logger):
        """Test ElevenLabs engine specifically"""
        engine = "elevenlabs"
        project_name = f"E2E_TEST_{engine.upper()}_{int(time.time())}"
        logger.start_engine_section(engine)

        try:
            success, error_msg = self._run_engine_test(logger, engine, project_name)
            if not success:
                logger.log_error(f"Pipeline failed: {error_msg}")

            assert success, f"Pipeline test failed for {engine}: {error_msg}"

            logger.test_results[engine] = {
                "project": project_name,
                "status": "PASS",
            }

        except Exception as e:
            logger.log_error(f"Exception in {engine} test", e)
            logger.test_results[engine] = {
                "status": "FAIL",
                "error": str(e),
            }
            raise

    def _check_engine_available(self, engine: str) -> bool:
        """Check if an engine is available"""
        try:
            if engine == "edge":
                import edge_tts

                return True
            elif engine == "gtts":
                import gtts

                return True
            elif engine == "xtts":
                try:
                    import TTS

                    return True
                except ImportError:
                    return False
            elif engine == "elevenlabs":
                return os.environ.get("ELEVENLABS_API_KEY") is not None
            return False
        except ImportError:
            return False

    def _run_cmd(self, args: list[str]) -> dict:
        """Run CLI command with proper environment using subprocess list args (no shell=True quoting issues)"""
        env = os.environ.copy()
        # Ensure src is in PYTHONPATH
        src_path = str((Path(__file__).parent.parent / "src").resolve())
        env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

        # Construct command list: [python, -m, audioformation, arg1, arg2...]
        cmd_list = [sys.executable, "-m", "audioformation"] + args

        try:
            result = subprocess.run(
                cmd_list,
                env=env,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            return {
                "cmd": " ".join(cmd_list),  # For logging display
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "cmd": " ".join(cmd_list),
                "returncode": -1,
                "stdout": "",
                "stderr": "Timeout expired",
                "success": False,
            }
        except Exception as e:
            return {
                "cmd": " ".join(cmd_list),
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }

    def _run_engine_test(
        self, logger, engine: str, project_name: str
    ) -> tuple[bool, str]:
        """Run complete pipeline test for one engine. Returns (success, error_msg)"""
        step_times = {}

        # Step 1: Bootstrap (Create project)
        step_name = "Bootstrap"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        # Pass pure strings, no quotes needed for list-based subprocess
        result = self._run_cmd(["new", project_name])
        step_times[step_name] = time.time() - start

        logger.log_command(f"new {project_name}", result)
        if not result["success"]:
            return False, f"Bootstrap failed: {result['stderr']}"

        # Step 2: Ingest
        step_name = "Ingest"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        source_path = str(TEST_SAMPLES_DIR.resolve())
        result = self._run_cmd(["ingest", project_name, "--source", source_path])
        step_times[step_name] = time.time() - start

        logger.log_command(f"ingest {project_name}", result)
        if not result["success"]:
            return False, f"Ingest failed: {result['stderr']}"

        # Step 3: Validate
        step_name = "Validate"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        result = self._run_cmd(["validate", project_name])
        step_times[step_name] = time.time() - start

        logger.log_command(f"validate {project_name}", result)
        if not result["success"]:
            # Log but don't fail immediately if validation warns?
            # Usually validate returns 0 even with warnings, 1 on fail.
            return False, f"Validation failed: {result['stderr']}"

        # Step 4: Generate
        step_name = "Generate"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        # Construct args
        gen_args = ["generate", project_name, "--engine", engine]
        if VOICES[engine]:
            gen_args.extend(["--voice", VOICES[engine]])

        result = self._run_cmd(gen_args)
        step_times[step_name] = time.time() - start

        logger.log_command(f"generate {project_name}", result)
        if not result["success"]:
            return False, f"Generate failed: {result['stderr']}"

        # Step 5: Process
        step_name = "Process"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        result = self._run_cmd(["process", project_name])
        step_times[step_name] = time.time() - start

        logger.log_command(f"process {project_name}", result)
        if not result["success"]:
            return False, f"Process failed: {result['stderr']}"

        # Step 6: Mix
        step_name = "Mix"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        result = self._run_cmd(["mix", project_name])
        step_times[step_name] = time.time() - start

        logger.log_command(f"mix {project_name}", result)
        if not result["success"]:
            return False, f"Mix failed: {result['stderr']}"

        # Step 7: Export
        step_name = "Export"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()

        # Just export MP3 for speed in E2E
        result = self._run_cmd(["export", project_name, "--format", "mp3"])
        step_times[step_name] = time.time() - start

        logger.log_command(f"export {project_name}", result)
        if not result["success"]:
            return False, f"Export failed: {result['stderr']}"
        else:
            self._log_export_files(logger, project_name)

        # Log timing summary
        logger.entries.append(f"\n**Timing Summary**:\n")
        for step, duration in step_times.items():
            logger.entries.append(f"- {step}: {duration:.2f}s\n")

        logger.end_engine_section(engine)
        return True, ""

    def _log_export_files(self, logger, project_name: str):
        """Log exported file information"""
        export_dirs = [
            Path("PROJECTS") / project_name / "07_EXPORT" / "audiobook",
            Path(project_name) / "07_EXPORT" / "audiobook",
        ]

        for export_dir in export_dirs:
            if export_dir.exists():
                logger.entries.append(f"\n**Exported Files**:\n")
                for fmt_file in export_dir.glob("*"):
                    if fmt_file.is_file():
                        file_info = logger.log_file_info(fmt_file)
                        logger.entries.append(
                            f"- {file_info['path']}: {file_info['size_mb']} MB\n"
                        )
                break


class TestEngineAvailability:
    """Test engine availability and configuration"""

    def test_edge_tts_availability(self):
        """Test Edge-TTS availability"""
        try:
            import edge_tts

            assert True, "Edge-TTS is available"
        except ImportError:
            pytest.skip("Edge-TTS not available")

    def test_gtts_availability(self):
        """Test gTTS availability"""
        try:
            import gtts

            assert True, "gTTS is available"
        except ImportError:
            pytest.skip("gTTS not available")

    def test_elevenlabs_api_key(self):
        """Test ElevenLabs API key configuration"""
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            pytest.skip("ElevenLabs API key not configured")
        # More flexible API key format check
        assert len(api_key) > 10, "API key seems too short"
        assert (
            api_key.replace("-", "").replace("_", "").isalnum()
        ), "API key contains invalid characters"

    def test_xtts_availability(self):
        """Test XTTS availability"""
        try:
            import TTS

            assert True, "XTTS is available"
        except ImportError:
            pytest.skip("XTTS not available")


class TestTestData:
    """Test data validation"""

    def test_test_samples_directory(self):
        """Test test samples directory exists"""
        assert TEST_SAMPLES_DIR.exists(), "Test samples directory not found"

    def test_required_test_files(self):
        """Test required test files exist"""
        required_files = ["contemplative.txt", "energetic.txt"]
        for filename in required_files:
            filepath = TEST_SAMPLES_DIR / filename
            assert filepath.exists(), f"Required test file missing: {filename}"
            assert filepath.stat().st_size > 0, f"Test file is empty: {filename}"
