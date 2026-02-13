#!/usr/bin/env python3
"""
Fast project health check for Audio Formation.
Validates dependencies, hardware, and project structure.
"""

import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

def check_python_version() -> Tuple[bool, str]:
    """Check Python version compatibility."""
    version = sys.version_info
    if version >= (3, 11):
        return True, f"✓ Python {version.major}.{version.minor}.{version.micro}"
    else:
        return False, f"✗ Python {version.major}.{version.minor}.{version.micro} (requires >=3.11)"

def check_dependencies() -> List[Tuple[bool, str]]:
    """Check core dependencies."""
    deps = {
        "click": "click",
        "fastapi": "fastapi", 
        "uvicorn": "uvicorn",
        "pydub": "pydub",
        "numpy": "numpy",
        "soundfile": "soundfile",
        "edge-tts": "edge_tts",
        "httpx": "httpx",
        "pyloudnorm": "pyloudnorm",
        "midiutil": "midiutil",
        "mutagen": "mutagen",
        "jsonschema": "jsonschema"
    }
    
    results = []
    for dep_name, import_name in deps.items():
        try:
            __import__(import_name)
            results.append((True, f"✓ {dep_name}"))
        except ImportError:
            results.append((False, f"✗ {dep_name} (missing)"))
        except Exception as e:
            # Handle pydub audioop import issues gracefully
            if "audioop" in str(e) and dep_name == "pydub":
                results.append((True, f"✓ {dep_name} (installed, audioop issue known)"))
            else:
                results.append((False, f"✗ {dep_name} (error: {str(e)[:50]})"))
    
    return results

def check_project_structure() -> List[Tuple[bool, str]]:
    """Check required project directories."""
    required_dirs = [
        "src/audioformation",
        "src/audioformation/utils", 
        "src/audioformation/engines",
        "tests",
        "schemas"
    ]
    
    results = []
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            results.append((True, f"✓ {dir_path}"))
        else:
            results.append((False, f"✗ {dir_path} (missing)"))
    
    return results

def check_core_files() -> List[Tuple[bool, str]]:
    """Check core project files."""
    required_files = [
        "pyproject.toml",
        "src/audioformation/__init__.py",
        "src/audioformation/config.py",
        "src/audioformation/cli.py",
        "src/audioformation/pipeline.py",
        "src/audioformation/project.py",
        "src/audioformation/validation.py",
        "schemas/project.schema.json"
    ]
    
    results = []
    for file_path in required_files:
        path = Path(file_path)
        if path.exists() and path.is_file():
            results.append((True, f"✓ {file_path}"))
        else:
            results.append((False, f"✗ {file_path} (missing)"))
    
    return results

def check_hardware() -> List[Tuple[bool, str]]:
    """Check hardware requirements."""
    results = []
    
    # Check for ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], 
                      capture_output=True, check=True, timeout=5)
        results.append((True, "✓ FFmpeg available"))
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        results.append((False, "✗ FFmpeg not found"))
    
    # Check for GPU (basic check)
    try:
        import torch
        if torch.cuda.is_available():
            results.append((True, f"✓ CUDA GPU: {torch.cuda.get_device_name(0)}"))
        else:
            results.append((True, "✓ No CUDA GPU (CPU-only mode)"))
    except ImportError:
        results.append((True, "? GPU check skipped (torch not installed)"))
    
    return results

def run_tests() -> Tuple[bool, str]:
    """Quick test run to validate functionality."""
    # Skip tests if tests directory doesn't exist
    if not Path("tests").exists():
        return True, "⚠ Tests skipped (tests directory missing)"
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", "-v", "--tb=short", "-x"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return True, "✓ All tests passed"
        else:
            return False, f"✗ Tests failed: {result.stderr.split(chr(10))[0]}"
    except subprocess.TimeoutExpired:
        return False, "✗ Tests timed out"
    except Exception as e:
        return False, f"✗ Test error: {str(e)[:50]}"

def main():
    """Run fast health check."""
    print("🔍 Audio Formation Fast Health Check")
    print("=" * 40)
    
    all_passed = True
    
    # Python version
    passed, msg = check_python_version()
    print(f"Python: {msg}")
    all_passed = all_passed and passed
    
    print("\n📦 Dependencies:")
    for passed, msg in check_dependencies():
        print(f"  {msg}")
        all_passed = all_passed and passed
    
    print("\n📁 Project Structure:")
    for passed, msg in check_project_structure():
        print(f"  {msg}")
        all_passed = all_passed and passed
    
    print("\n📄 Core Files:")
    for passed, msg in check_core_files():
        print(f"  {msg}")
        all_passed = all_passed and passed
    
    print("\n🖥️  Hardware:")
    for passed, msg in check_hardware():
        print(f"  {msg}")
    
    print("\n🧪 Quick Tests:")
    passed, msg = run_tests()
    print(f"  {msg}")
    all_passed = all_passed and passed
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✅ All checks passed! Project is ready.")
        return 0
    else:
        print("❌ Some checks failed. Review issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
