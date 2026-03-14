from fastapi.testclient import TestClient
from audioformation.server.app import app
from audioformation.config import PROJECTS_ROOT

def test_safe_static_files_blocks_sensitive_config():
    # Create test project with 00_CONFIG
    test_proj = PROJECTS_ROOT / "test_proj"
    config_dir = test_proj / "00_CONFIG"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "engines.json").write_text('{"api_key": "secret"}')
    (config_dir / "hardware.json").write_text('{"gpu": "rtx"}')
    (config_dir / ".env").write_text('SECRET=1')

    # Create allowed file
    export_dir = test_proj / "07_EXPORT"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "audio.mp3").write_text('fake audio')
    (export_dir / "manifest.json").write_text('{"version": 1}')

    client = TestClient(app)

    # These should be blocked (403 or 404, depending on how FastAPI handles it, but our override raises 403)
    r1 = client.get("/projects/test_proj/00_CONFIG/engines.json")
    assert r1.status_code == 403

    r2 = client.get("/projects/test_proj/00_config/engines.json")
    assert r2.status_code == 403

    r3 = client.get("/projects/test_proj/00_CONFIG/.env")
    assert r3.status_code == 403

    # Direct access to engines.json in another dir should still be blocked just in case
    (test_proj / "engines.json").write_text('{}')
    r4 = client.get("/projects/test_proj/engines.json")
    assert r4.status_code == 403

    # Allowed access
    r_ok = client.get("/projects/test_proj/07_EXPORT/audio.mp3")
    assert r_ok.status_code == 200

    r_json = client.get("/projects/test_proj/07_EXPORT/manifest.json")
    assert r_json.status_code == 200
