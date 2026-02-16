#!/usr/bin/env python3
"""
Quick Test Runner for Audio-Formation
Runs core tests while skipping problematic ones
"""

import subprocess
import sys
from pathlib import Path

def run_tests():
    """Run tests with sensible defaults"""
    
    print("🧪 Audio-Formation Test Runner")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("src").exists():
        print("❌ Not in project root directory")
        return False
    
    # Run unit tests only (skip E2E and dashboard tests)
    print("📋 Running Unit Tests...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-k", "not e2e and not dashboard",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-fail-under=60"
    ]
    
    try:
        result = subprocess.run(cmd, cwd=".", capture_output=False)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
