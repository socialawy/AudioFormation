"""Comprehensive tests for FastAPI server routes using TestClient."""

import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Import the FastAPI app
try:
    from audioformation.server.app import app
    from audioformation.engines.registry import registry
    from audioformation.engines.base import GenerationResult

    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False
    app = None
    registry = None
    GenerationResult = None


@pytest.fixture
def mock_engine():
    """Mock TTS engine for testing."""
    engine = MagicMock()
    engine.supports_cloning = True
    engine.supports_ssml = True
    engine.requires_gpu = False
    engine.list_voices = AsyncMock(
        return_value=[{"id": "test-voice", "name": "Test Voice", "language": "en"}]
    )
    engine.generate = AsyncMock(
        return_value=GenerationResult(
            success=True, output_path=Path("/tmp/test.wav"), duration_sec=1.0
        )
    )
    return engine


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "id": "TEST_PROJECT",
        "title": "Test Project",
        "chapters": [
            {
                "id": "chapter1",
                "title": "Chapter 1",
                "language": "en",
                "source": "01_TEXT/chapters/chapter1.txt",
                "character": "narrator",
            }
        ],
        "characters": {
            "narrator": {
                "name": "Narrator",
                "engine": "edge",
                "voice": "en-US-AriaNeural",
            }
        },
        "generation": {"chunk_max_chars": 200, "engine": "edge"},
        "mix": {"target_lufs": -16},
        "export": {"formats": ["mp3"], "mp3_bitrate": 192},
    }


@pytest.mark.skipif(not SERVER_AVAILABLE, reason="Server dependencies not available")
class TestServerRoutes:
    """Comprehensive tests for all 22 server endpoints."""

    # ==================== Project CRUD Tests ====================

    def test_list_projects(self, client, sample_project):
        """Test GET /projects - List all projects."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        project_ids = [p["id"] for p in projects]
        assert sample_project["id"] in project_ids

    def test_create_project(self, client, isolate_projects):
        """Test POST /projects - Create new project."""
        project_id = "NEW_TEST_PROJECT"
        response = client.post("/api/projects", json={"id": project_id})

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == project_id
        assert "path" in data
        assert "message" in data

        # Verify project was created
        project_path = isolate_projects / project_id
        assert project_path.exists()
        assert (project_path / "project.json").exists()

    def test_create_duplicate_project(self, client, sample_project):
        """Test POST /projects - Create duplicate project should fail."""
        response = client.post("/api/projects", json={"id": sample_project["id"]})
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_get_project_details(self, client, sample_project):
        """Test GET /projects/{project_id} - Get project details."""
        response = client.get(f"/api/projects/{sample_project['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_project["id"]
        assert "chapters" in data
        assert "characters" in data

    def test_get_nonexistent_project(self, client):
        """Test GET /projects/{project_id} - Nonexistent project."""
        response = client.get("/api/projects/NONEXISTENT")
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    def test_update_project(self, client, sample_project, sample_project_data):
        """Test PUT /projects/{project_id} - Update project."""
        project_id = sample_project["id"]

        # Get current project data
        response = client.get(f"/api/projects/{project_id}")
        current_data = response.json()

        # Modify data
        current_data["mix"]["target_lufs"] = -20.0

        # Update project
        response = client.put(f"/api/projects/{project_id}", json=current_data)
        assert response.status_code == 200
        assert "updated successfully" in response.json()["message"]

        # Verify update
        response = client.get(f"/api/projects/{project_id}")
        updated_data = response.json()
        assert updated_data["mix"]["target_lufs"] == -20.0

    def test_update_project_id_mismatch(self, client, sample_project):
        """Test PUT /projects/{project_id} - ID mismatch in body."""
        response = client.put(
            f"/api/projects/{sample_project['id']}",
            json={"id": "DIFFERENT_ID", "data": "test"},
        )
        assert response.status_code == 400
        assert "Project ID mismatch" in response.json()["detail"]

    # ==================== Pipeline Operation Tests ====================

    def test_ingest_files(self, client, sample_project):
        """Test POST /projects/{project_id}/ingest - Ingest text files."""
        project_id = sample_project["id"]

        # Create test files
        test_content = "This is test content for ingestion."
        files = [
            ("files", ("test1.txt", test_content, "text/plain")),
            ("files", ("test2.txt", test_content, "text/plain")),
        ]

        with patch("audioformation.server.routes._ingest_files_sync") as mock_ingest:
            mock_ingest.return_value = {"ingested": 2, "message": "Success"}

            response = client.post(f"/api/projects/{project_id}/ingest", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Ingest started" in data["message"]

    def test_ingest_nonexistent_project(self, client):
        """Test POST /projects/{project_id}/ingest - Nonexistent project."""
        response = client.post("/api/projects/NONEXISTENT/ingest")
        assert response.status_code in [
            404,
            422,
        ]  # 404 for project not found, 422 for validation error

    def test_upload_file_references(self, client, sample_project):
        """Test POST /projects/{project_id}/upload - Upload reference files."""
        project_id = sample_project["id"]
        test_content = b"mock audio data"

        with patch("audioformation.server.routes.sanitize_filename") as mock_sanitize:
            mock_sanitize.return_value = "test_reference.wav"

            response = client.post(
                f"/api/projects/{project_id}/upload?category=references",
                files={"file": ("test.wav", test_content, "audio/wav")},
            )

            assert response.status_code == 200
            data = response.json()
            assert "path" in data
            assert "filename" in data
            assert "02_VOICES/references" in data["path"]

    def test_upload_file_music(self, client, sample_project):
        """Test POST /projects/{project_id}/upload - Upload music files."""
        project_id = sample_project["id"]
        test_content = b"mock music data"

        with patch("audioformation.server.routes.sanitize_filename") as mock_sanitize:
            mock_sanitize.return_value = "test_music.wav"

            response = client.post(
                f"/api/projects/{project_id}/upload?category=music",
                files={"file": ("music.wav", test_content, "audio/wav")},
            )

            assert response.status_code == 200
            data = response.json()
            assert "05_MUSIC/generated" in data["path"]

    def test_upload_file_invalid_category(self, client, sample_project):
        """Test POST /projects/{project_id}/upload - Invalid category."""
        response = client.post(
            f"/api/projects/{sample_project['id']}/upload?category=invalid",
            files={"file": ("test.txt", "content", "text/plain")},
        )
        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]

    def test_preview_voice(self, client, sample_project, mock_engine):
        """Test POST /projects/{project_id}/preview - Generate voice preview."""
        project_id = sample_project["id"]

        with patch(
            "audioformation.server.routes.registry.get", return_value=mock_engine
        ):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

                mock_engine.generate.return_value = GenerationResult(
                    success=True, output_path=tmp_path, duration_sec=1.0
                )

                preview_request = {
                    "text": "This is a preview test",
                    "engine": "edge",
                    "voice": "en-US-AriaNeural",
                    "language": "en",
                }

                response = client.post(
                    f"/api/projects/{project_id}/preview", json=preview_request
                )

                assert response.status_code == 200
                assert response.headers["content-type"] == "audio/wav"

    def test_preview_voice_invalid_engine(self, client, sample_project):
        """Test POST /projects/{project_id}/preview - Invalid engine."""
        project_id = sample_project["id"]

        preview_request = {
            "text": "This is a preview test",
            "engine": "invalid_engine",
            "voice": "test",
            "language": "en",
        }

        response = client.post(
            f"/api/projects/{project_id}/preview", json=preview_request
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_trigger_generation(self, client, sample_project):
        """Test POST /projects/{project_id}/generate - Trigger TTS generation."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes.generate_project") as mock_generate:
            mock_generate.return_value = None

            generate_request = {"chapters": ["chapter1"], "engine": "edge"}

            response = client.post(
                f"/api/projects/{project_id}/generate", json=generate_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Generation started" in data["message"]

    def test_trigger_mix(self, client, sample_project):
        """Test POST /projects/{project_id}/mix - Trigger mixing."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes.mix_project") as mock_mix:
            mock_mix.return_value = None

            response = client.post(f"/api/projects/{project_id}/mix")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Mixing started" in data["message"]

    def test_trigger_validate(self, client, sample_project):
        """Test POST /projects/{project_id}/validate - Run validation."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes.validate_project") as mock_validate:
            mock_validate.return_value = None

            response = client.post(f"/api/projects/{project_id}/validate")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Validation started" in data["message"]

    def test_trigger_process(self, client, sample_project):
        """Test POST /projects/{project_id}/process - Run audio processing."""
        project_id = sample_project["id"]

        with patch(
            "audioformation.server.routes.batch_process_project"
        ) as mock_process:
            mock_process.return_value = None

            response = client.post(f"/api/projects/{project_id}/process")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Processing started" in data["message"]

    def test_trigger_compose(self, client, sample_project):
        """Test POST /projects/{project_id}/compose - Generate background music."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes.generate_pad") as mock_compose:
            mock_compose.return_value = None

            compose_request = {"preset": "contemplative", "duration": 60}

            response = client.post(
                f"/api/projects/{project_id}/compose", json=compose_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Composing" in data["message"]

    def test_trigger_sfx(self, client, sample_project):
        """Test POST /projects/{project_id}/sfx - Generate sound effects."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes.generate_sfx") as mock_sfx:
            mock_sfx.return_value = None

            sfx_request = {"type": "whoosh", "duration": 1.0, "name": "test_whoosh"}

            response = client.post(f"/api/projects/{project_id}/sfx", json=sfx_request)

            assert response.status_code == 200
            data = response.json()
            assert "Generated SFX" in data["message"]
            assert "path" in data

    # ==================== Export & QC Tests ====================

    def test_trigger_export_mp3(self, client, sample_project):
        """Test POST /projects/{project_id}/export - Export MP3."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes.export_project_mp3") as mock_export:
            mock_export.return_value = None

            export_request = {"format": "mp3", "bitrate": 192}

            response = client.post(
                f"/api/projects/{project_id}/export", json=export_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Export started (mp3)" in data["message"]

    def test_trigger_export_m4b(self, client, sample_project):
        """Test POST /projects/{project_id}/export - Export M4B."""
        project_id = sample_project["id"]

        with patch(
            "audioformation.server.routes.export_project_m4b_auto"
        ) as mock_export:
            mock_export.return_value = None

            export_request = {"format": "m4b", "bitrate": 128}

            response = client.post(
                f"/api/projects/{project_id}/export", json=export_request
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "Export started (m4b)" in data["message"]

    def test_trigger_qc_scan(self, client, sample_project):
        """Test POST /projects/{project_id}/qc-scan - Run QC scan."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes._qc_scan_sync") as mock_qc:
            mock_qc.return_value = {
                "message": "QC scan completed",
                "scanned": 5,
                "passed": 4,
                "warned": 1,
                "failed": 0,
            }

            response = client.post(f"/api/projects/{project_id}/qc-scan")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "QC scan started" in data["message"]

    def test_get_qc_reports(self, client, sample_project):
        """Test GET /projects/{project_id}/qc - Get QC reports."""
        project_id = sample_project["id"]

        # Mock QC reports
        project_path = sample_project["dir"]
        gen_dir = project_path / "03_GENERATED"
        gen_dir.mkdir(parents=True, exist_ok=True)

        qc_report = {
            "project_id": project_id,
            "chunks": [
                {"chunk_id": "chunk1", "status": "pass"},
                {"chunk_id": "chunk2", "status": "warn"},
            ],
        }

        (gen_dir / "qc_report_test.json").write_text(
            json.dumps(qc_report, indent=2), encoding="utf-8"
        )

        response = client.get(f"/api/projects/{project_id}/qc")
        assert response.status_code == 200
        data = response.json()
        assert "chunk_qc" in data
        assert len(data["chunk_qc"]) > 0

    def test_get_qc_reports_none(self, client, sample_project):
        """Test GET /projects/{project_id}/qc - No QC reports found."""
        project_id = sample_project["id"]

        response = client.get(f"/api/projects/{project_id}/qc")
        assert response.status_code == 200
        data = response.json()
        assert "No QC reports found" in data["message"]

    def test_trigger_qc_final(self, client, sample_project):
        """Test POST /projects/{project_id}/qc-final - Run final QC."""
        project_id = sample_project["id"]

        with patch("audioformation.server.routes._qc_final_sync") as mock_qc:
            mock_qc.return_value = {
                "passed": True,
                "total_files": 3,
                "failed_files": 0,
                "results": [],
            }

            response = client.post(f"/api/projects/{project_id}/qc-final")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "QC Final started" in data["message"]

    # ==================== Status & Files Tests ====================

    def test_get_project_status(self, client, sample_project):
        """Test GET /projects/{project_id}/status - Get pipeline status."""
        project_id = sample_project["id"]

        response = client.get(f"/api/projects/{project_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "bootstrap" in data["nodes"]
        assert data["nodes"]["bootstrap"]["status"] == "complete"

    def test_list_project_files(self, client, sample_project):
        """Test GET /projects/{project_id}/files - List project files."""
        project_id = sample_project["id"]

        # Create some test files
        project_path = sample_project["dir"]

        # Create export files
        export_dir = project_path / "07_EXPORT" / "audiobook"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "test.mp3").write_bytes(b"mock audio data")

        # Create music files
        music_dir = project_path / "05_MUSIC" / "generated"
        music_dir.mkdir(parents=True, exist_ok=True)
        (music_dir / "background.wav").write_bytes(b"mock music data")

        response = client.get(f"/api/projects/{project_id}/files")
        assert response.status_code == 200
        files = response.json()
        assert isinstance(files, list)

        # Check that files are properly categorized
        categories = [f["category"] for f in files]
        assert "audiobook" in categories
        assert "music" in categories

    def test_get_project_hardware(self, client, sample_project):
        """Test GET /projects/{project_id}/hardware - Get hardware info."""
        project_id = sample_project["id"]

        # Create hardware.json
        project_path = sample_project["dir"]
        config_dir = project_path / "00_CONFIG"
        config_dir.mkdir(parents=True, exist_ok=True)

        hardware_info = {
            "gpu": {"available": False},
            "cpu": {"cores": 8},
            "memory": {"total_gb": 16},
        }

        (config_dir / "hardware.json").write_text(
            json.dumps(hardware_info, indent=2), encoding="utf-8"
        )

        response = client.get(f"/api/projects/{project_id}/hardware")
        assert response.status_code == 200
        data = response.json()
        assert "gpu" in data
        assert "cpu" in data

    def test_get_project_hardware_none(self, client, sample_project):
        """Test GET /projects/{project_id}/hardware - No hardware file."""
        project_id = sample_project["id"]

        response = client.get(f"/api/projects/{project_id}/hardware")
        assert response.status_code == 200
        data = response.json()
        assert data == {}

    # ==================== Engine API Tests ====================

    def test_list_engines(self, client, mock_engine):
        """Test GET /engines - List available TTS engines."""
        with patch(
            "audioformation.server.routes.registry.list_available",
            return_value=["edge"],
        ):
            with patch(
                "audioformation.server.routes.registry.get", return_value=mock_engine
            ):
                response = client.get("/api/engines")
                assert response.status_code == 200

                engines = response.json()
                assert isinstance(engines, list)
                assert len(engines) > 0

                engine = engines[0]
                assert "id" in engine
                assert "cloning" in engine
                assert "ssml" in engine
                assert "gpu" in engine

    def test_list_engines_with_error(self, client):
        """Test GET /engines - Engine loading error."""
        with patch(
            "audioformation.server.routes.registry.list_available",
            return_value=["broken_engine"],
        ):
            with patch(
                "audioformation.server.routes.registry.get",
                side_effect=Exception("Engine error"),
            ):
                response = client.get("/api/engines")
                assert response.status_code == 200

                engines = response.json()
                assert len(engines) == 1
                assert engines[0]["id"] == "broken_engine"
                assert "error" in engines[0]

    def test_list_engine_voices(self, client, mock_engine):
        """Test GET /engines/{name}/voices - List engine voices."""
        engine_name = "edge"

        with patch(
            "audioformation.server.routes.registry.get", return_value=mock_engine
        ):
            response = client.get(f"/api/engines/{engine_name}/voices")
            assert response.status_code == 200

            voices = response.json()
            assert isinstance(voices, list)
            assert len(voices) > 0

            voice = voices[0]
            assert "id" in voice
            assert "name" in voice

    def test_list_engine_voices_with_lang(self, client, mock_engine):
        """Test GET /engines/{name}/voices - List voices with language filter."""
        engine_name = "edge"
        lang = "en"

        mock_engine.list_voices.return_value = [
            {"id": "en-voice", "name": "English Voice", "language": "en"}
        ]

        with patch(
            "audioformation.server.routes.registry.get", return_value=mock_engine
        ):
            response = client.get(f"/api/engines/{engine_name}/voices?lang={lang}")
            assert response.status_code == 200

            voices = response.json()
            assert len(voices) == 1
            assert voices[0]["language"] == "en"

    def test_list_engine_voices_not_found(self, client):
        """Test GET /engines/{name}/voices - Engine not found."""
        response = client.get("/api/engines/nonexistent/voices")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    # ==================== Error Handling Tests ====================

    def test_all_endpoints_nonexistent_project(self, client):
        """Test that all project endpoints return appropriate errors for nonexistent projects."""

        # Test each endpoint with appropriate HTTP method
        endpoints_and_methods = [
            ("/api/projects/NONEXISTENT", "GET"),
            ("/api/projects/NONEXISTENT/ingest", "POST"),
            ("/api/projects/NONEXISTENT/upload", "POST"),
            ("/api/projects/NONEXISTENT/preview", "POST"),
            ("/api/projects/NONEXISTENT/generate", "POST"),
            ("/api/projects/NONEXISTENT/mix", "POST"),
            ("/api/projects/NONEXISTENT/validate", "POST"),
            ("/api/projects/NONEXISTENT/process", "POST"),
            ("/api/projects/NONEXISTENT/compose", "POST"),
            ("/api/projects/NONEXISTENT/sfx", "POST"),
            ("/api/projects/NONEXISTENT/export", "POST"),
            ("/api/projects/NONEXISTENT/qc-scan", "POST"),
            ("/api/projects/NONEXISTENT/qc", "GET"),
            ("/api/projects/NONEXISTENT/qc-final", "POST"),
            ("/api/projects/NONEXISTENT/status", "GET"),
            ("/api/projects/NONEXISTENT/files", "GET"),
            ("/api/projects/NONEXISTENT/hardware", "GET"),
        ]

        for endpoint, method in endpoints_and_methods:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)

            # Accept 404 (not found), 422 (validation error), or 405 (method not allowed for some endpoints)
            assert response.status_code in [
                404,
                422,
                405,
            ], f"Endpoint {endpoint} should return 404, 422, or 405"
