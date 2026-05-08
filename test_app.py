from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path
from src.audioformation.server.app import SafeStaticFiles

app = FastAPI()

app.mount("/", SafeStaticFiles(directory=Path("tests")), name="static")

client = TestClient(app)

response = client.get("/test_server_routes.py")
print("Response status:", response.status_code)
# Try accessing via 'None' path, this happens if a request goes through differently?
