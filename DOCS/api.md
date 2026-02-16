# AudioFormation API Reference

**Base URL:** `http://localhost:4001`

## Health

### `GET /health`
Returns server status and version.

```json
{"status": "ok", "version": "0.3.0"}
```

## Projects

### `GET /api/projects`
List all projects.

### `POST /api/projects`

Create a new project.

Body:

```json
{"id": "MY_NOVEL"}
```

### `GET /api/projects/{id}`
Get project configuration (project.json).

### `PUT /api/projects/{id}`
Update project configuration.

Body: Full or partial project.json object.

## Pipeline

### `POST /api/projects/{id}/ingest`
Upload and ingest text files.

Content-Type: multipart/form-data
Field: files — one or more .txt files.

### `POST /api/projects/{id}/validate`
Run validation gate (Node 2). Returns pass/fail with details.

### `POST /api/projects/{id}/generate`
Trigger TTS generation (Node 3). Runs in background.

Body (optional):

```json
{"engine": "edge", "chapters": ["ch01", "ch02"]}
```

### `POST /api/projects/{id}/process`
Run audio normalization (Node 4). Runs in background.

### `POST /api/projects/{id}/compose`
Generate ambient background music (Node 5). Runs in background.

Body (optional):

```json
{"preset": "contemplative", "duration": 60}
```

Available presets: contemplative, tense, wonder, melancholy, triumph

### `POST /api/projects/{id}/mix`
Mix voice + music with VAD ducking (Node 6). Runs in background.

### `POST /api/projects/{id}/qc-final`
Run QC Final gate (Node 7). Returns results synchronously.

### `POST /api/projects/{id}/export`
Export final audio (Node 8). Runs in background.

Body (optional):

```json
{"format": "m4b", "bitrate": 128}
```

## Status & QC

### `GET /api/projects/{id}/status`
Get pipeline status (pipeline-status.json).

### `GET /api/projects/{id}/qc`
Get QC reports (chunk scan + final mix).

## Audio Files

Audio files are served directly via static mount:

```
GET /projects/{PROJECT_ID}/03_GENERATED/raw/ch01.wav
GET /projects/{PROJECT_ID}/06_MIX/renders/ch01.wav
GET /projects/{PROJECT_ID}/07_EXPORT/chapters/ch01.mp3
```

## Dashboard

The web dashboard is served at http://localhost:4001/ (root).

Tabs: Projects | Editor | Mix & Review