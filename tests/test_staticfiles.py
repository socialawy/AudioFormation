import pytest
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from audioformation.server.staticfiles import SafeStaticFiles

def test_safe_staticfiles(tmp_path):
    # Setup test directory structure
    (tmp_path / "00_CONFIG").mkdir()
    (tmp_path / "00_CONFIG" / "secret.json").write_text('{"key": "value"}')
    (tmp_path / "07_EXPORT").mkdir()
    (tmp_path / "07_EXPORT" / "audio.mp3").write_text("audio data")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "file.txt").write_text("hidden")
    (tmp_path / "normal.txt").write_text("normal")
    (tmp_path / "script.py").write_text("print('hello')")

    app = FastAPI()
    app.mount("/projects", SafeStaticFiles(directory=str(tmp_path)), name="projects")
    client = TestClient(app)

    # 1. Allowed file
    response = client.get("/projects/normal.txt")
    assert response.status_code == 200
    assert response.text == "normal"

    # Allowed export
    response = client.get("/projects/07_EXPORT/audio.mp3")
    assert response.status_code == 200
    assert response.text == "audio data"

    # 2. Block 00_CONFIG
    response = client.get("/projects/00_CONFIG/secret.json")
    assert response.status_code == 403

    # 3. Block hidden files/folders
    response = client.get("/projects/.hidden/file.txt")
    assert response.status_code == 403

    # 4. Block python scripts
    response = client.get("/projects/script.py")
    assert response.status_code == 403
