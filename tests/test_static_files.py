
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from audioformation.server.app import app
from audioformation.config import PROJECTS_ROOT

class TestSafeStaticFiles:

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def sensitive_project(self):
        """Create a project with sensitive files."""
        project_id = "SECURITY_TEST_PROJECT"
        project_path = PROJECTS_ROOT / project_id
        project_path.mkdir(parents=True, exist_ok=True)

        # 1. Sensitive file in blocked directory
        config_dir = project_path / "00_CONFIG"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "engines.json").write_text('{"secret": "FAIL"}')

        # 2. Hidden file
        (project_path / ".secret").write_text("hidden")

        # 3. Sensitive extension
        (project_path / "script.py").write_text("print('hacked')")

        # 4. Safe file
        (project_path / "safe.txt").write_text("safe content")

        yield project_id

        # Cleanup
        import shutil
        if project_path.exists():
            shutil.rmtree(project_path)

    def test_block_sensitive_directory(self, client, sensitive_project):
        """Test blocking access to 00_CONFIG."""
        response = client.get(f"/projects/{sensitive_project}/00_CONFIG/engines.json")
        assert response.status_code == 404

    def test_block_hidden_files(self, client, sensitive_project):
        """Test blocking access to hidden files."""
        response = client.get(f"/projects/{sensitive_project}/.secret")
        assert response.status_code == 404

    def test_block_sensitive_extensions(self, client, sensitive_project):
        """Test blocking access to .py files."""
        response = client.get(f"/projects/{sensitive_project}/script.py")
        assert response.status_code == 404

    def test_allow_safe_files(self, client, sensitive_project):
        """Test allowing access to safe files."""
        response = client.get(f"/projects/{sensitive_project}/safe.txt")
        assert response.status_code == 200
        assert response.text == "safe content"

    def test_allow_generated_files(self, client, sensitive_project):
        """Test allowing access to generated audio files."""
        project_path = PROJECTS_ROOT / sensitive_project
        gen_dir = project_path / "03_GENERATED" / "raw"
        gen_dir.mkdir(parents=True, exist_ok=True)
        (gen_dir / "audio.wav").write_bytes(b"RIFF")

        response = client.get(f"/projects/{sensitive_project}/03_GENERATED/raw/audio.wav")
        assert response.status_code == 200
