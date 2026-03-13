
import sys
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

# We need to mock dependencies before importing app
from unittest.mock import MagicMock
if "edge_tts" not in sys.modules:
    sys.modules["edge_tts"] = MagicMock()
    sys.modules["soundfile"] = MagicMock()
    sys.modules["pyloudnorm"] = MagicMock()
    sys.modules["pydub"] = MagicMock()
    sys.modules["gtts"] = MagicMock()

def test_sensitive_file_protection(tmp_path):
    """
    Test that sensitive files in 00_CONFIG are protected (403),
    while legitimate files are accessible.
    """
    # 1. Setup simulated environment
    projects_root = tmp_path / "PROJECTS"
    projects_root.mkdir(exist_ok=True)

    # 2. Create a project with various files
    proj_dir = projects_root / "VULN_PROJECT"

    # Sensitive
    config_dir = proj_dir / "00_CONFIG"
    config_dir.mkdir(parents=True, exist_ok=True)
    sensitive_file = config_dir / "engines.json"
    sensitive_file.write_text('{"api_key": "SUPER_SECRET_KEY"}', encoding="utf-8")

    # Allowed
    export_dir = proj_dir / "07_EXPORT"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (export_dir / "audio.mp3").write_text("fake_audio", encoding="utf-8")

    # Hidden/Blocked
    (proj_dir / ".env").write_text("SECRET=1", encoding="utf-8")

    # Force reload of app to ensure it picks up the patched path
    if "audioformation.server.app" in sys.modules:
        del sys.modules["audioformation.server.app"]

    with patch("audioformation.config.PROJECTS_ROOT", projects_root):
        from audioformation.server.app import app

        client = TestClient(app)

        # 3. Check Sensitive Directory -> Blocked
        response = client.get("/projects/VULN_PROJECT/00_CONFIG/engines.json")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        assert "Access Forbidden" in response.text

        # 4. Check Manifest.json -> Allowed
        response = client.get("/projects/VULN_PROJECT/07_EXPORT/manifest.json")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # 5. Check Audio File -> Allowed
        response = client.get("/projects/VULN_PROJECT/07_EXPORT/audio.mp3")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # 6. Check Hidden File -> Blocked
        response = client.get("/projects/VULN_PROJECT/.env")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
