"""
E2E Test Logging and Metrics Capture Utility
Captures command execution, file outputs, audio metrics, and timing
"""

import json
import os
import sys
import subprocess
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import platform


class E2ELogger:
    """Comprehensive logging for e2e tests with metrics capture"""

    def __init__(self, output_file: str = "E2E_TEST_LOG.md"):
        self.output_file = Path(output_file)
        self.entries = []
        self.start_time = datetime.now()
        self.engine_results = {}
        self.system_info = self._capture_system_info()

    def _capture_system_info(self) -> Dict[str, str]:
        """Capture system context"""
        return {
            "timestamp": self.start_time.isoformat(),
            "os": platform.system(),
            "python_version": sys.version.split()[0],
            "cwd": os.getcwd(),
            "platform": platform.platform(),
        }

    def log_section(self, title: str, level: int = 1):
        """Start a new section"""
        heading = "#" * level
        self.entries.append(f"\n{heading} {title}\n")

    def log_step(
        self,
        step_name: str,
        status: str,
        duration: float,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log a pipeline step result"""
        self.entries.append(f"\n#### {step_name}\n")
        self.entries.append(f"- **Status**: {status}\n")
        self.entries.append(f"- **Duration**: {duration:.2f}s\n")

        if details:
            for key, value in details.items():
                if isinstance(value, dict):
                    self.entries.append(f"- **{key}**:\n")
                    for k, v in value.items():
                        self.entries.append(f"    - {k}: {v}\n")
                elif isinstance(value, list):
                    self.entries.append(f"- **{key}**:\n")
                    for item in value:
                        self.entries.append(f"    - {item}\n")
                else:
                    self.entries.append(f"- **{key}**: {value}\n")

    def log_audio_metrics(self, filename: str, metrics: Dict[str, Any]):
        """Log audio metrics for a file"""
        self.entries.append(f"\n**Audio Metrics: {filename}**\n")
        self.entries.append("```\n")
        for key, value in metrics.items():
            if isinstance(value, float):
                self.entries.append(f"  {key}: {value:.2f}\n")
            else:
                self.entries.append(f"  {key}: {value}\n")
        self.entries.append("```\n")

    def log_file_info(self, filepath: Path) -> Dict[str, Any]:
        """Capture file size, checksum, and other info"""
        if not filepath.exists():
            return {"status": "missing", "path": str(filepath)}

        stat = filepath.stat()
        with open(filepath, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()[:8]

        try:
            return {
                "path": str(filepath.relative_to(Path.cwd())),
                "size_bytes": stat.st_size,
                "size_mb": f"{stat.st_size / (1024*1024):.2f}",
                "sha256_prefix": checksum,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        except ValueError:
            # Fallback if path is not relative to cwd
            return {
                "path": str(filepath),
                "size_bytes": stat.st_size,
                "size_mb": f"{stat.st_size / (1024*1024):.2f}",
                "sha256_prefix": checksum,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }

    def log_error(self, error_msg: str, exception: Optional[Exception] = None):
        """Log an error"""
        self.entries.append(f"\n⚠️ **ERROR**: {error_msg}\n")
        if exception:
            self.entries.append(f"```\n{str(exception)}\n```\n")

    def log_skip(self, reason: str):
        """Log a skipped step"""
        self.entries.append(f"\n⏭️ **SKIPPED**: {reason}\n")

    def start_engine_section(self, engine_name: str):
        """Start logging for a specific engine"""
        self.engine_results[engine_name] = {"start_time": time.time(), "steps": []}
        self.log_section(f"Engine: {engine_name}", level=2)

    def end_engine_section(self, engine_name: str):
        """Finish logging for an engine"""
        if engine_name in self.engine_results:
            duration = time.time() - self.engine_results[engine_name]["start_time"]
            self.entries.append(f"\n**Total Duration**: {duration:.2f}s\n")

    def log_command(self, cmd: str, result: Optional[Dict[str, Any]] = None):
        """Log a CLI command execution"""
        self.entries.append(f"\n**Command**: `{cmd}`\n")
        if result:
            if result.get("returncode") == 0:
                self.entries.append("✅ Success\n")
            else:
                self.entries.append(
                    f"❌ Failed (exit code: {result.get('returncode')})\n"
                )

            if result.get("stdout"):
                self.entries.append(f"```\n{result['stdout'][:200]}...\n```\n")
            if result.get("stderr"):
                self.entries.append(
                    f"**stderr**: ```\n{result['stderr'][:200]}...\n```\n"
                )

    def log_validation_results(self, results: Dict[str, Any]):
        """Log validation gate results"""
        self.entries.append("\n**Validation Results**:\n")
        self.entries.append("```json\n")
        self.entries.append(json.dumps(results, indent=2))
        self.entries.append("\n```\n")

    def add_comparison_table(
        self, engines: List[str], metrics: Dict[str, Dict[str, Any]]
    ):
        """Add a side-by-side comparison table"""
        self.log_section("Comparative Results", level=2)
        self.entries.append("\n| Metric | " + " | ".join(engines) + " |\n")
        self.entries.append("|--------|" + "|".join(["-----"] * len(engines)) + "|\n")

        # Collect all metric keys
        all_keys = set()
        for engine_metrics in metrics.values():
            all_keys.update(engine_metrics.keys())

        for key in sorted(all_keys):
            row = [key]
            for engine in engines:
                value = metrics.get(engine, {}).get(key, "N/A")
                if isinstance(value, float):
                    row.append(f"{value:.2f}")
                else:
                    row.append(str(value))
            self.entries.append("| " + " | ".join(row) + " |\n")

    def save(self):
        """Write log to markdown file"""
        content = self._generate_header()
        content += "".join(self.entries)
        content += self._generate_footer()

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Test log saved to: {self.output_file.absolute()}")

    def _generate_header(self) -> str:
        """Generate markdown header"""
        header = f"""# E2E Audio-Formation Pipeline Test Log

**Test Execution Details**
- **Date**: {self.system_info['timestamp']}
- **OS**: {self.system_info['os']}
- **Python**: {self.system_info['python_version']}
- **Working Directory**: {self.system_info['cwd']}

---

## Test Overview

This comprehensive e2e test validates the full Audio-Formation pipeline across all 4 TTS engines:
- **Edge-TTS** (Cloud, primary)
- **gTTS** (Cloud, fallback)
- **XTTS v2** (Local, voice cloning)
- **ElevenLabs** (Cloud, premium)

Each engine runs: Bootstrap → Ingest → Validate → Generate → Process → Compose → Mix → QC Final → Export

**Test Data**: Short Arabic samples with diacritics (contemplative.txt, energetic.txt)

---

"""
        return header

    def _generate_footer(self) -> str:
        """Generate markdown footer with summary"""
        total_duration = (datetime.now() - self.start_time).total_seconds()
        footer = f"""

---

## Summary

- **Total Execution Time**: {total_duration:.2f}s
- **Engines Tested**: {len(self.engine_results)}
- **Test Data Location**: `./test_samples/`
- **Log Generated**: {datetime.now().isoformat()}

---

*Generated by Audio-Formation E2E Test Suite*
"""
        return footer


def execute_command(
    cmd: str,
    timeout: int = 900,
    max_retries: int = 2,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Execute a CLI command and capture output with retry logic for network operations"""

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            return {
                "cmd": cmd,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "attempt": attempt + 1,
            }
        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                # Retry for network operations (TTS generation, etc.)
                time.sleep(5)  # Brief delay before retry
                continue
            return {
                "cmd": cmd,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s (attempt {attempt + 1}/{max_retries + 1})",
                "success": False,
                "attempt": attempt + 1,
            }
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return {
                "cmd": cmd,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
                "attempt": attempt + 1,
            }
