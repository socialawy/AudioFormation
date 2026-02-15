
# AudioFormation Build Log

**Status:** Phase 3 In Progress (Dashboard Editor)  
**Tests:** 351 / 351 Passing (100%)  
**Date:** February 14, 2026  
**Hardware Reference:** NVIDIA GTX 1650 Ti (4GB VRAM)

---

##  Recent Activity (Feb 14, 2026)

**Phase 3: Web Dashboard (Editor)**
*   **Editor UI:** Added editor view to dashboard (`src/audioformation/server/static/`).
    *   Configuration tabs for Generation and Mix settings.
    *   Chapter list view.
    *   Raw JSON editor mode.
*   **API:** Added `PUT /api/projects/{id}` endpoint to save project configuration.
*   **Logic:** Implemented `app.js` logic for loading, editing, and saving projects via the API.
*   **Tests:** Added API update tests (`tests/test_server.py`).

**Phase 3: Web Dashboard (Started)**
*   **Frontend:** Created minimal HTML/JS/CSS dashboard (`src/audioformation/server/static/`).
*   **Static Serving:** Updated `app.py` to mount static files at root `/`.
*   **Dependencies:** Added `aiofiles` to server group for `StaticFiles` support.
*   **Features:** Project listing and creation now working via UI.

**Phase 3: Server (Completed)**
*   **FastAPI:** Implemented core API server (`src/audioformation/server/app.py`).
*   **Routes:** Added project CRUD endpoints (`list`, `create`, `get`, `status`).
*   **CLI:** Added `serve` command to launch the API server (`audioformation serve`).
*   **Testing:** Verified API endpoints with `tests/test_server.py`.

**Phase 3: Mixing & Export (Completed)**
*   **QC Final:** Implemented strict validation for mixed audio.
*   **M4B Export:** Built full audiobook export pipeline with `ffmpeg`.
*   **Refactor:** Decoupled `generate.py` from CLI calls.

**Phase 3: Mixing Engine**
*   **Feature:** Implemented `src/audioformation/audio/mixer.py` providing multi-track mixing.
*   **Feature:** Added **VAD-based ducking** using `silero-vad`.
*   **Feature:** Implemented `energy` fallback for ducking.
*   **CLI:** Added `audioformation mix` command (Node 6).

**Final Polish (Phase 2):**
*   **Test Suite Fixed:** Resolved persistent failures. All 351 tests pass.
*   **CLI Commands:** Fully implemented `cast`, `compose`, `preview`, and `compare`.

---

## 🚀 Current Status: Phase 3 (Core) Complete

The entire CLI pipeline is operational. The Web Dashboard now includes a functional editor.

**Next Steps (Phase 3 Dashboard):**
1.  **Dashboard Timeline:** Integrate wavesurfer.js for mixing visualization.

---

## 🏗️ Phase 2: Advanced Audio (Completed)

**Goal:** Bridge the gap between "TTS output" and "Audiobook production" via voice cloning, mixing, and ambient sound.

| # | Item | Status | Description |
| :--- | :--- | :--- | :--- |
| **1** | **Pipeline Status Wiring** | ✅ Done | `new`, `ingest`, `qc` now write to `pipeline-status.json`. |
| **2** | **Fallback Scope** | ✅ Done | Changed from per-chunk to **per-chapter** (regenerate full chapter on fail). |
| **3** | **Dependencies** | ✅ Done | Pinned `edge-tts>=7.0` (DRM fix) & `transformers<5` (XTTS compat). |
| **4** | **Crossfade Overrides** | ✅ Done | Tuned per engine: Edge (120ms), XTTS (80ms), gTTS (150ms). |
| **5** | **Arabic Pipeline** | ✅ Done | Mishkal integration + smart boundary splitting (sentence detection). |
| **6** | **Ambient Composer** | ✅ Done | Pure Numpy generator. 5 presets (Zen, Tense, Dark, etc.). |
| **7** | **XTTS v2 Integration** | ✅ Done | Full engine with VRAM management, generation params, and comprehensive tests. |
| **8** | **Multi-Speaker Wiring** | ✅ Done | Per-segment character resolution with engine-specific routing. |
| **9** | **CLI Finalization** | ✅ Done | `cast`, `compose`, `preview`, `compare` commands exposed. |

### 🔬 Decision Record: XTTS Feasibility Spike
*Run Date: Feb 2026 | Hardware: GTX 1650 Ti (4GB)*

*   **Result:** **GO** 🟢
*   **VRAM Strategy:** `empty_cache_per_chapter` is mandatory.
*   **Load Time:** ~15s (cached).
*   **Generation:** ~3.8s per Arabic chunk (excellent speed).
*   **Headroom:** ~1.5 GB VRAM free during generation.
*   **Conclusion:** The hardware can support XTTS v2 for production if we strictly manage VRAM clearing between chapters.

---

## 🏛️ Phase 1: Foundation (Completed)

**Focus:** Core architecture, CLI scaffolding, and generic TTS support.

### 📦 Final Inventory (43 Files)
*   **Core:** `cli.py`, `pipeline.py`, `project.py`, `config.py`
*   **Engines:** `base.py`, `registry.py`, `edge_tts.py`, `gtts_engine.py`
*   **Utils:** `text.py`, `arabic.py`, `hardware.py`, `security.py`
*   **Processing:** `processor.py` (LUFS/Trim), `scanner.py` (QC)

### 🛠️ Critical Fixes Log (Phase 1)

| Fix # | Issue | Solution |
| :--- | :--- | :--- |
| **12** | **Edge-TTS 403 Forbidden** | Upgraded to `edge-tts` v7 (updated Sec-MS-GEC token). |
| **13** | **Emergency Fallback** | Integrated `gTTS` engine (Google Translate) as a no-auth backup. |
| **10** | **Validation Gates** | Added defensive schema checks for malformed `project.json`. |

---

## 🔮 Roadmap (Immediate Next Steps)

### Phase 3: Server & Dashboard (Planned)
- FastAPI server + REST endpoints (`localhost:4001`)
- Web dashboard (vanilla HTML/JS) with wavesurfer.js timeline (`localhost:4000`)
- FXForge (SFX domain — procedural + sample import)

### 🎯 Recent Completion: Multi-Speaker Integration (Feb 14, 2026)

**Key Features Implemented:**
- **Per-Segment Character Resolution:** Each `[speaker_id]` tag routes to specific character → engine → voice
- **Engine Tracking:** Tracks all engines used per chapter for proper VRAM cleanup
- **Fallback Handling:** Unknown characters fall back to chapter default engine
- **Backward Compatibility:** Single mode chapters work unchanged
- **Text Format:** Simple `[speaker_id]` tags on separate lines, blank lines revert to default
- **VRAM Management:** Enhanced to handle multiple engines per chapter
- **Test Coverage:** 13 dedicated multi-speaker tests covering parsing, generation, edge cases

### 🧪 Real-World Validation: Novel End-to-End Test (Feb 14, 2026)

**Test Project:** THE_NEXT_PLACE  
**Content:** Arabic novel introduction (3,129 chars, philosophical text)  
**Pipeline:** Full end-to-end run (validate → generate → qc → process → export)

| Step | Status | Details |
|:---|:---|:---|
| **Validate** | ✅ | 6 passed, 1 warning (undiacritized Arabic) |
| **Generate** | ✅ | 16 chunks, edge→gtts fallback, QC passed |
| **QC Scan** | ✅ | 0% failure rate, all quality checks passed |
| **Process** | ✅ | Normalized to -16.0 LUFS, silence trimmed |
| **Export** | ✅ | MP3 exported at 192kbps with metadata |

**Generated Output:**
- `ch01_intro.wav` (26.8 MB) - Full chapter, stitched with 120ms crossfade
- `ch01_intro.mp3` - Final export, processed and normalized
- QC report: 10 passed, 6 warnings (LUFS deviation within tolerance)
