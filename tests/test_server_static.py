
"""Tests for static file serving and security controls."""

import pytest
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

# Import app - if dependencies are missing, skip tests
try:
    from audioformation.server.app import app
    from audioformation.config import PROJECTS_ROOT
    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False

@pytest.fixture
def client():
    """Create a TestClient instance."""
    return TestClient(app)

@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project with sensitive and public files."""
    # We need to use the actual PROJECTS_ROOT used by app, or mock it.
    # config.PROJECTS_ROOT is imported in app.py.
    # To avoid messing with real PROJECTS directory, we can use the fact that
    # app.mount uses the object passed to it.

    # However, app.py uses PROJECTS_ROOT from config.
    # We can temporarily create a directory in the real PROJECTS_ROOT or
    # try to mock the mount.

    # Simpler: Create a test project in the real PROJECTS_ROOT and clean it up.
    project_id = "TEST_STATIC_SECURITY"
    project_path = PROJECTS_ROOT / project_id

    if project_path.exists():
        shutil.rmtree(project_path)

    project_path.mkdir(parents=True, exist_ok=True)

    # Create structure
    (project_path / "00_CONFIG").mkdir()
    (project_path / "03_GENERATED").mkdir()

    yield project_path

    # Cleanup
    if project_path.exists():
        shutil.rmtree(project_path)

@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not installed")
def test_access_sensitive_config(client, temp_project):
    """Test blocking access to 00_CONFIG."""
    project_id = temp_project.name

    # Create sensitive file
    secret_file = temp_project / "00_CONFIG" / "engines.json"
    secret_file.write_text('{"secret": "key"}')

    response = client.get(f"/projects/{project_id}/00_CONFIG/engines.json")
    assert response.status_code == 403

@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not installed")
def test_access_hidden_file(client, temp_project):
    """Test blocking access to hidden files."""
    project_id = temp_project.name

    # Create hidden file
    hidden_file = temp_project / ".env"
    hidden_file.write_text("SECRET=123")

    response = client.get(f"/projects/{project_id}/.env")
    assert response.status_code == 403

@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not installed")
def test_access_hidden_directory(client, temp_project):
    """Test blocking access to hidden directories."""
    project_id = temp_project.name

    # Create hidden dir
    hidden_dir = temp_project / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config").write_text("content")

    response = client.get(f"/projects/{project_id}/.git/config")
    assert response.status_code == 403

@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not installed")
def test_access_source_code(client, temp_project):
    """Test blocking access to .py files."""
    project_id = temp_project.name

    # Create python file
    py_file = temp_project / "script.py"
    py_file.write_text("print('hello')")

    response = client.get(f"/projects/{project_id}/script.py")
    assert response.status_code == 403

@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not installed")
def test_access_public_file(client, temp_project):
    """Test allowing access to safe public files."""
    project_id = temp_project.name

    # Create public file
    public_file = temp_project / "03_GENERATED" / "output.wav"
    public_file.write_text("fake audio")

    response = client.get(f"/projects/{project_id}/03_GENERATED/output.wav")
    assert response.status_code == 200
    assert response.text == "fake audio"

@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not installed")
def test_path_traversal_attempt(client, temp_project):
    """Test path traversal attempts."""
    project_id = temp_project.name

    # Attempt to go up
    # Note: TestClient handles paths, but requests usually normalize ..
    # Starlette/FastAPI static files protect against traversal by default,
    # but we want to make sure our custom class doesn't break it.

    response = client.get(f"/projects/{project_id}/../00_CONFIG/engines.json")
    # Should be 404 or 403 depending on normalization, but definitely not 200
    assert response.status_code != 200
