#!/usr/bin/env python3
"""
E2E Dashboard API Tests for Audio-Formation
Tests all pipeline endpoints using REST API calls
"""

import json
import os
import time
import requests
import hashlib
import pytest
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Load environment variables from .env file
def load_env():
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# Configuration
BASE_URL = "http://localhost:4001/api"
TEST_SAMPLES_DIR = Path(__file__).parent.parent / "test_samples"

# Check for ElevenLabs API key
ENGINES = ["edge", "gtts", "xtts"]
if os.environ.get("ELEVENLABS_API_KEY"):
    ENGINES.append("elevenlabs")

EXPORT_FORMATS = ["mp3"]  # Start with one format for speed

# Generate unique project names with timestamp
TIMESTAMP = datetime.now().strftime("%H%M%S")


@pytest.mark.skipif(
    not os.environ.get("SKIP_DASHBOARD_TESTS") is None,
    reason="Dashboard tests skipped - set SKIP_DASHBOARD_TESTS to skip"
)
class TestDashboardAPI:
    """Test Dashboard API endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create a requests session for API testing"""
        session = requests.Session()
        yield session
        session.close()
    
    def test_server_health(self, session: requests.Session):
        """Test if dashboard server is running"""
        try:
            response = session.get(f"{BASE_URL.replace('/api', '')}/health", timeout=5)
            assert response.status_code == 200, f"Dashboard server not running on {BASE_URL}"
            assert response.json()["status"] == "ok"
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Dashboard server not running on {BASE_URL}")
    
    def test_create_project(self, session: requests.Session) -> bool:
        """Test project creation"""
        project_id = f"API_TEST_CREATE_{TIMESTAMP}"
        print(f"📝 Creating project: {project_id}")
        
        response = session.post(f"{BASE_URL}/projects", json={"id": project_id})
        success = response.status_code == 201
        
        if success:
            data = response.json()
            assert data["id"] == project_id
            assert "path" in data
            print(f"✅ Project created: {data}")
        else:
            print(f"❌ Project creation failed: {response.status_code} - {response.text}")
        
        return success
    
    def test_ingest(self, session: requests.Session) -> bool:
        """Test file ingestion"""
        project_id = f"API_TEST_INGEST_{TIMESTAMP}"
        
        # Create project first
        session.post(f"{BASE_URL}/projects", json={"id": project_id})
        
        print(f"📥 Ingesting files for: {project_id}")
        
        # Prepare files for upload
        files = []
        test_files = ["contemplative.txt", "energetic.txt"]
        
        for filename in test_files:
            filepath = TEST_SAMPLES_DIR / filename
            if filepath.exists():
                files.append(('files', (filename, open(filepath, 'rb'), 'text/plain')))
        
        if not files:
            print("❌ No test files found")
            return False
        
        response = session.post(f"{BASE_URL}/projects/{project_id}/ingest", files=files)
        
        # Close files
        for _, (_, file_obj, _) in files:
            file_obj.close()
        
        success = response.status_code == 200
        if success:
            result = response.json()
            print(f"✅ Ingested: {result}")
        else:
            print(f"❌ Ingest failed: {response.status_code} - {response.text}")
        
        return success
    
    def test_validate(self, session: requests.Session) -> bool:
        """Test project validation"""
        project_id = f"API_TEST_VALIDATE_{TIMESTAMP}"
        
        # Create and ingest project first
        session.post(f"{BASE_URL}/projects", json={"id": project_id})
        
        # Ingest files
        files = []
        for filename in ["contemplative.txt", "energetic.txt"]:
            filepath = TEST_SAMPLES_DIR / filename
            if filepath.exists():
                files.append(('files', (filename, open(filepath, 'rb'), 'text/plain')))
        
        if files:
            session.post(f"{BASE_URL}/projects/{project_id}/ingest", files=files)
            for _, (_, file_obj, _) in files:
                file_obj.close()
        
        print(f"✅ Validating project: {project_id}")
        
        response = session.post(f"{BASE_URL}/projects/{project_id}/validate")
        success = response.status_code == 200
        
        if success:
            result = response.json()
            print(f"✅ Validation result: {result}")
        else:
            print(f"❌ Validation failed: {response.status_code} - {response.text}")
        
        return success
    
    def test_generate(self, session: requests.Session, engine: str) -> bool:
        """Test TTS generation"""
        project_id = f"API_TEST_GEN_{engine.upper()}_{TIMESTAMP}"
        
        # Setup project
        session.post(f"{BASE_URL}/projects", json={"id": project_id})
        
        # Ingest files
        files = []
        for filename in ["contemplative.txt", "energetic.txt"]:
            filepath = TEST_SAMPLES_DIR / filename
            if filepath.exists():
                files.append(('files', (filename, open(filepath, 'rb'), 'text/plain')))
        
        if files:
            session.post(f"{BASE_URL}/projects/{project_id}/ingest", files=files)
            for _, (_, file_obj, _) in files:
                file_obj.close()
        
        session.post(f"{BASE_URL}/projects/{project_id}/validate")
        
        print(f"🎤 Generating audio with {engine}: {project_id}")
        
        payload = {"engine": engine}
        
        # Configure voice parameters per engine
        if engine == "edge":
            payload["voice"] = "ar-EG-SalmaNeural"
        elif engine == "gtts":
            payload["voice"] = "ar"
        elif engine == "xtts":
            payload["voice"] = "default"
        elif engine == "elevenlabs":
            payload["voice"] = "arabic-female"
        
        response = session.post(f"{BASE_URL}/projects/{project_id}/generate", json=payload)
        
        success = response.status_code == 200
        if success:
            result = response.json()
            print(f"✅ Generation started: {result}")
            return self._wait_for_completion(session, project_id, "generate")
        else:
            print(f"❌ Generation failed: {response.status_code} - {response.text}")
            return False
    
    def test_process(self, session: requests.Session) -> bool:
        """Test audio processing"""
        project_id = f"API_TEST_PROCESS_{TIMESTAMP}"
        
        # Setup project with audio
        self._setup_project_with_audio(session, project_id, "edge")
        
        print(f"🔧 Processing audio: {project_id}")
        
        response = session.post(f"{BASE_URL}/projects/{project_id}/process")
        success = response.status_code == 200
        
        if success:
            result = response.json()
            print(f"✅ Processing started: {result}")
            return self._wait_for_completion(session, project_id, "process")
        else:
            print(f"❌ Process failed: {response.status_code} - {response.text}")
            return False
    
    def test_mix(self, session: requests.Session) -> bool:
        """Test audio mixing"""
        project_id = f"API_TEST_MIX_{TIMESTAMP}"
        
        # Setup project with processed audio
        self._setup_project_with_audio(session, project_id, "edge")
        session.post(f"{BASE_URL}/projects/{project_id}/process")
        self._wait_for_completion(session, project_id, "process")
        
        print(f"🎵 Mixing audio: {project_id}")
        
        response = session.post(f"{BASE_URL}/projects/{project_id}/mix")
        success = response.status_code == 200
        
        if success:
            result = response.json()
            print(f"✅ Mixing started: {result}")
            return self._wait_for_completion(session, project_id, "mix")
        else:
            print(f"❌ Mix failed: {response.status_code} - {response.text}")
            return False
    
    def test_export(self, session: requests.Session) -> bool:
        """Test audio export"""
        project_id = f"API_TEST_EXPORT_{TIMESTAMP}"
        
        # Setup complete project
        self._setup_complete_project(session, project_id)
        
        print(f"📤 Exporting audio: {project_id}")
        
        response = session.post(f"{BASE_URL}/projects/{project_id}/export", json={"format": "mp3"})
        success = response.status_code == 200
        
        if success:
            result = response.json()
            print(f"✅ Export started: {result}")
            return self._wait_for_completion(session, project_id, "export")
        else:
            print(f"❌ Export failed: {response.status_code} - {response.text}")
            return False
    
    def _setup_project_with_audio(self, session: requests.Session, project_id: str, engine: str):
        """Helper to setup a project with generated audio"""
        session.post(f"{BASE_URL}/projects", json={"id": project_id})
        
        # Ingest files
        files = []
        for filename in ["contemplative.txt", "energetic.txt"]:
            filepath = TEST_SAMPLES_DIR / filename
            if filepath.exists():
                files.append(('files', (filename, open(filepath, 'rb'), 'text/plain')))
        
        if files:
            session.post(f"{BASE_URL}/projects/{project_id}/ingest", files=files)
            for _, (_, file_obj, _) in files:
                file_obj.close()
        
        session.post(f"{BASE_URL}/projects/{project_id}/validate")
        
        # Generate audio
        payload = {"engine": engine}
        if engine == "edge":
            payload["voice"] = "ar-EG-SalmaNeural"
        elif engine == "gtts":
            payload["voice"] = "ar"
        
        session.post(f"{BASE_URL}/projects/{project_id}/generate", json=payload)
        self._wait_for_completion(session, project_id, "generate")
    
    def _setup_complete_project(self, session: requests.Session, project_id: str):
        """Helper to setup a complete project with all steps"""
        self._setup_project_with_audio(session, project_id, "edge")
        session.post(f"{BASE_URL}/projects/{project_id}/process")
        self._wait_for_completion(session, project_id, "process")
        session.post(f"{BASE_URL}/projects/{project_id}/mix")
        self._wait_for_completion(session, project_id, "mix")
    
    def _wait_for_completion(self, session: requests.Session, project_id: str, operation: str, timeout: int = 300) -> bool:
        """Wait for background operation to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = session.get(f"{BASE_URL}/projects/{project_id}/status")
            if response.status_code == 200:
                status = response.json()
                node_status = status.get("nodes", {}).get(operation, {}).get("status")
                
                if node_status == "complete":
                    print(f"✅ {operation} completed successfully")
                    return True
                elif node_status == "failed":
                    print(f"❌ {operation} failed")
                    return False
                elif node_status in ["running", "partial"]:
                    print(f"⏳ Waiting for {operation} to complete...")
                    time.sleep(5)
                    continue
            
            time.sleep(2)
        
        print(f"⏰ {operation} timed out after {timeout} seconds")
        return False


# Engine-specific tests
@pytest.mark.parametrize("engine", ["edge", "gtts", "xtts"])
class TestEngineSpecific:
    """Test specific TTS engines"""
    
    def test_engine_generation(self, session, engine):
        """Test generation for specific engine"""
        api_test = TestDashboardAPI()
        success = api_test.test_generate(session, engine)
        assert success, f"Generation failed for engine {engine}"


# Skip ElevenLabs test if no API key
@pytest.mark.skipif(
    not os.environ.get("ELEVENLABS_API_KEY"),
    reason="ElevenLabs API key not configured"
)
class TestElevenLabs:
    """Test ElevenLabs engine specifically"""
    
    def test_elevenlabs_generation(self, session):
        """Test ElevenLabs generation"""
        api_test = TestDashboardAPI()
        success = api_test.test_generate(session, "elevenlabs")
        assert success, "ElevenLabs generation failed"
