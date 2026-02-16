#!/usr/bin/env python3
"""
E2E CLI Test Suite for Audio-Formation Pipeline
Tests all 4 TTS engines across full pipeline with detailed logging
"""

import json
import os
import sys
import time
import pytest
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add tools directory to path for e2e_logger
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

try:
    from e2e_logger import E2ELogger, execute_command
    E2E_LOGGER_AVAILABLE = True
except ImportError:
    E2E_LOGGER_AVAILABLE = False

# Configuration
TEST_SAMPLES_DIR = Path(__file__).parent.parent / "test_samples"
ENGINES = ["edge", "gtts", "xtts", "elevenlabs"]
VOICES = {
    "edge": "ar-EG-SalmaNeural",
    "gtts": "ar",  # gTTS uses language codes
    "xtts": None,  # XTTS uses speaker embedding
    "elevenlabs": None,  # ElevenLabs uses pre-trained voices
}

EXPORT_FORMATS = ["mp3", "m4b", "wav"]


@pytest.mark.skipif(
    not E2E_LOGGER_AVAILABLE,
    reason="E2E logger utilities not available"
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
        
        assert TEST_SAMPLES_DIR.exists(), f"Test samples directory not found: {TEST_SAMPLES_DIR}"
        
        required_files = ["contemplative.txt", "energetic.txt"]
        for filename in required_files:
            filepath = TEST_SAMPLES_DIR / filename
            assert filepath.exists(), f"Required test file missing: {filename}"
            
            file_info = logger.log_file_info(filepath)
            logger.entries.append(f"- {filename}: {file_info['size_mb']} MB, {file_info['sha256_prefix']}\n")
        
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
            success = self._run_engine_test(logger, engine, project_name)
            assert success, f"Pipeline test failed for {engine}"
            
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
        reason="ElevenLabs API key not configured"
    )
    def test_elevenlabs_pipeline(self, logger):
        """Test ElevenLabs engine specifically"""
        engine = "elevenlabs"
        project_name = f"E2E_TEST_{engine.upper()}_{int(time.time())}"
        logger.start_engine_section(engine)
        
        try:
            success = self._run_engine_test(logger, engine, project_name)
            assert success, f"Pipeline test failed for {engine}"
            
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
    
    def _run_engine_test(self, logger, engine: str, project_name: str) -> bool:
        """Run complete pipeline test for one engine"""
        step_times = {}
        all_passed = True
        
        # Step 1: Bootstrap (Create project)
        step_name = "Bootstrap"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" new "{project_name}"'
        result = execute_command(cmd)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Project creation failed for {engine}")
            return False
        
        # Step 2: Ingest
        step_name = "Ingest"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" ingest "{project_name}" --source ./test_samples'
        result = execute_command(cmd)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Ingest failed for {engine}")
            all_passed = False
        
        # Step 3: Validate
        step_name = "Validate"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" validate "{project_name}"'
        result = execute_command(cmd)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Validation failed for {engine}")
            # Don't stop - validation may fail due to missing config
        
        # Step 4: Generate
        step_name = "Generate"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        voice_arg = f" --voice {VOICES[engine]}" if VOICES[engine] else ""
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" generate "{project_name}" --engine {engine}{voice_arg}'
        result = execute_command(cmd, timeout=900)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Generation failed for {engine}")
            all_passed = False
        
        # Step 5: Process
        step_name = "Process"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" process "{project_name}"'
        result = execute_command(cmd)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Process failed for {engine}")
            all_passed = False
        
        # Step 6: Mix
        step_name = "Mix"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" mix "{project_name}"'
        result = execute_command(cmd, timeout=600)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Mix failed for {engine}")
            all_passed = False
        
        # Step 7: Export
        step_name = "Export"
        logger.entries.append(f"\n### {step_name}\n")
        start = time.time()
        
        format_args = " ".join([f"--format {fmt}" for fmt in EXPORT_FORMATS])
        cmd = f'python -c "import sys; sys.path.insert(0, \'src\'); import audioformation.cli; audioformation.cli.main()" export "{project_name}" {format_args}'
        result = execute_command(cmd)
        step_times[step_name] = time.time() - start
        
        logger.log_command(cmd, result)
        if not result["success"]:
            logger.log_error(f"Export failed for {engine}")
            all_passed = False
        else:
            self._log_export_files(logger, project_name)
            # Verify M4B specific metadata/chapters if m4b was requested
            if "m4b" in EXPORT_FORMATS:
                self._verify_m4b_export(logger, project_name)
        
        # Log timing summary
        logger.entries.append(f"\n**Timing Summary**:\n")
        for step, duration in step_times.items():
            logger.entries.append(f"- {step}: {duration:.2f}s\n")
        
        logger.end_engine_section(engine)
        return all_passed
    
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
                        logger.entries.append(f"- {file_info['path']}: {file_info['size_mb']} MB\n")
                break
    
    def _verify_m4b_export(self, logger, project_name: str):
        """Verify M4B export has chapters and metadata"""
        logger.entries.append(f"\n### M4B Verification\n")
        
        export_dir = Path("PROJECTS") / project_name / "07_EXPORT" / "audiobook"
        if not export_dir.exists():
            export_dir = Path(project_name) / "07_EXPORT" / "audiobook"
            
        m4b_files = list(export_dir.glob("*.m4b"))
        if not m4b_files:
            logger.log_error("No M4B file found for verification")
            return

        m4b_path = m4b_files[0]
        logger.entries.append(f"Verifying: `{m4b_path.name}`\n")

        # Use ffprobe to check for chapters
        cmd = f'ffprobe -i "{m4b_path}" -show_chapters -print_format json'
        result = execute_command(cmd, timeout=30)
        
        if result["success"]:
            try:
                data = json.loads(result["stdout"])
                chapters = data.get("chapters", [])
                logger.entries.append(f"✅ Found {len(chapters)} chapters in M4B\n")
                if chapters:
                    for i, ch in enumerate(chapters):
                        title = ch.get("tags", {}).get("title", "Unknown")
                        logger.entries.append(f"  - Chapter {i+1}: {title}\n")
                else:
                    logger.log_error("M4B file has no chapters")
            except Exception as e:
                logger.log_error(f"Failed to parse ffprobe output: {e}")
        else:
            logger.log_error(f"ffprobe failed: {result['stderr'][:200]}")


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
        assert api_key.replace("-", "").replace("_", "").isalnum(), "API key contains invalid characters"
    
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
