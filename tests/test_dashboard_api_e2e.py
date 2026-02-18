#!/usr/bin/env python3
"""
E2E Dashboard API Tests for Audio-Formation
Tests all pipeline endpoints using REST API calls
"""

import os
import time
import requests
import pytest
from pathlib import Path
from datetime import datetime


# Load environment variables from .env file
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


load_env()

# Configuration
BASE_URL = "http://localhost:4001/api"
# Ensure test samples dir exists in current working dir or relative to test file
TEST_SAMPLES_DIR = (Path(__file__).parent.parent / "test_samples").resolve()

# Generate unique project names with timestamp
TIMESTAMP = datetime.now().strftime("%H%M%S")


@pytest.fixture(scope="module")
def session():
    """Create a requests session for API testing"""
    s = requests.Session()
    yield s
    s.close()


@pytest.fixture(scope="module")
def ensure_test_data():
    """Ensure test samples exist."""
    TEST_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "contemplative.txt": "This is a quiet, contemplative scene. The wind whispers.",
        "energetic.txt": "Action! Movement! Fast paced dialogue happening now!",
    }

    for name, content in files.items():
        p = TEST_SAMPLES_DIR / name
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    yield


class DashboardAPIClient:
    """Helper class to interact with the API."""

    def __init__(self, session):
        self.session = session

    def check_health(self):
        return self.session.get(f"{BASE_URL.replace('/api', '')}/health", timeout=5)

    def create_project(self, project_id):
        return self.session.post(f"{BASE_URL}/projects", json={"id": project_id})

    def ingest(self, project_id, filenames):
        files = []
        opened_files = []

        for name in filenames:
            p = TEST_SAMPLES_DIR / name
            if p.exists():
                f = open(p, "rb")
                opened_files.append(f)
                files.append(("files", (name, f, "text/plain")))

        if not files:
            return None

        try:
            return self.session.post(
                f"{BASE_URL}/projects/{project_id}/ingest", files=files
            )
        finally:
            for f in opened_files:
                f.close()

    def validate(self, project_id):
        return self.session.post(f"{BASE_URL}/projects/{project_id}/validate")

    def generate(self, project_id, engine, voice=None):
        payload = {"engine": engine}
        if voice:
            payload["voice"] = voice
        return self.session.post(
            f"{BASE_URL}/projects/{project_id}/generate", json=payload
        )

    def process(self, project_id):
        return self.session.post(f"{BASE_URL}/projects/{project_id}/process")

    def mix(self, project_id):
        return self.session.post(f"{BASE_URL}/projects/{project_id}/mix")

    def export(self, project_id, fmt="mp3"):
        return self.session.post(
            f"{BASE_URL}/projects/{project_id}/export", json={"format": fmt}
        )

    def get_status(self, project_id):
        return self.session.get(f"{BASE_URL}/projects/{project_id}/status")

    def wait_for_completion(
        self, project_id: str, operation: str, timeout: int = 300
    ) -> bool:
        """Wait for background operation to complete"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = self.get_status(project_id)
            if response.status_code == 200:
                status = response.json()
                node_status = status.get("nodes", {}).get(operation, {}).get("status")

                if node_status == "complete":
                    return True
                elif node_status == "failed":
                    # Optionally log failure reason if needed
                    return False
                elif node_status in ["running", "partial", "pending"]:
                    time.sleep(2)
                    continue
            else:
                return False

            time.sleep(2)

        return False


@pytest.fixture(scope="module")
def api_client(session):
    client = DashboardAPIClient(session)
    # Perform health check before running tests
    try:
        client.check_health()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pytest.skip(f"Dashboard server not running on {BASE_URL}")
    return client


@pytest.mark.skipif(
    os.environ.get("SKIP_DASHBOARD_TESTS") is not None, reason="Dashboard tests skipped"
)
class TestDashboardE2E:
    """End-to-End tests for the Dashboard API."""

    def test_server_health(self, api_client):
        # Health check already passed in fixture
        resp = api_client.check_health()
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_full_pipeline_flow(self, api_client, ensure_test_data):
        """Test the standard linear pipeline."""
        project_id = f"API_FLOW_{TIMESTAMP}"

        # 1. Create
        assert api_client.create_project(project_id).status_code == 201

        # 2. Ingest
        assert api_client.ingest(project_id, ["contemplative.txt"]).status_code == 200

        # 3. Validate
        assert api_client.validate(project_id).status_code == 200

        # 4. Generate (using edge as default fast engine)
        gen_resp = api_client.generate(project_id, "edge", "ar-EG-SalmaNeural")
        assert gen_resp.status_code == 200
        assert api_client.wait_for_completion(project_id, "generate")

        # 5. Process
        assert api_client.process(project_id).status_code == 200
        assert api_client.wait_for_completion(project_id, "process")

        # 6. Mix
        assert api_client.mix(project_id).status_code == 200
        assert api_client.wait_for_completion(project_id, "mix")

        # 7. Export
        assert api_client.export(project_id).status_code == 200
        assert api_client.wait_for_completion(project_id, "export")


@pytest.mark.skipif(
    os.environ.get("SKIP_DASHBOARD_TESTS") is not None, reason="Dashboard tests skipped"
)
class TestEngineSpecific:
    """Parametrized tests for different engines via API."""

    @pytest.mark.parametrize("engine", ["edge", "gtts"])
    def test_engine_generation(self, api_client, ensure_test_data, engine):
        """Test generation for specific engine"""
        project_id = f"API_ENG_{engine.upper()}_{TIMESTAMP}"

        api_client.create_project(project_id)
        api_client.ingest(project_id, ["contemplative.txt"])
        api_client.validate(project_id)

        voice = "ar-EG-SalmaNeural" if engine == "edge" else "ar"

        resp = api_client.generate(project_id, engine, voice)
        assert resp.status_code == 200
        assert api_client.wait_for_completion(project_id, "generate")

    @pytest.mark.skipif(not os.environ.get("ELEVENLABS_API_KEY"), reason="No API Key")
    def test_elevenlabs_generation(self, api_client, ensure_test_data):
        project_id = f"API_ENG_11LABS_{TIMESTAMP}"
        api_client.create_project(project_id)
        api_client.ingest(project_id, ["contemplative.txt"])
        api_client.validate(project_id)

        resp = api_client.generate(project_id, "elevenlabs", "arabic-female")
        assert resp.status_code == 200
        assert api_client.wait_for_completion(project_id, "generate")
