"""
Pytest configuration and shared fixtures for Audio-Formation tests.
"""

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Redirect PROJECTS_ROOT to a temp directory for every test.

    Prevents tests from touching the real filesystem.
    Returns the temporary projects root.
    """
    test_root = tmp_path / "PROJECTS"
    test_root.mkdir(exist_ok=True)  # ← exist_ok=True prevents conflict

    # Monkeypatch the config module's PROJECTS_ROOT
    import audioformation.config as cfg
    monkeypatch.setattr(cfg, "PROJECTS_ROOT", test_root)

    # Also patch it in project.py (which imports it at module level)
    import audioformation.project as proj_mod
    monkeypatch.setattr(proj_mod, "PROJECTS_ROOT", test_root)

    # Patch in ingest.py if it imports directly
    try:
        import audioformation.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "PROJECTS_ROOT", test_root, raising=False)
    except (ImportError, AttributeError):
        pass

    # Patch in generate.py if it imports directly
    try:
        import audioformation.generate as gen_mod
        monkeypatch.setattr(gen_mod, "PROJECTS_ROOT", test_root, raising=False)
    except (ImportError, AttributeError):
        pass

    return test_root
