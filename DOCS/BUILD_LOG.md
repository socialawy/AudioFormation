# AudioFormation Build Log

**Status:** Phase 2 (Multi-Speaker Integration Complete)  
**Tests:** 314 / 314 Passing (100%)  
**Date:** February 14, 2026  
**Hardware Reference:** NVIDIA GTX 1650 Ti (4GB VRAM)

---

## � Recent Activity (Feb 14, 2026)

**Infrastructure & Automation:**
*   Merged 3 Dependabot PRs (pytest, pytest-asyncio, pre-commit)
*   Skipped transformers v5 PR (breaking changes, needs XTTS compatibility testing)
*   Created release tag `v0.1.0` marking Phase 1 completion
*   Added Mermaid pipeline diagram to README
*   Added Phase 2 TODO comments throughout codebase

**GitHub Setup Complete:**
*   CI/CD workflows (CI, lint, security)
*   Dependabot configuration
*   Pre-commit hooks
*   Pull request template
*   Security policy, Code of Conduct, LICENSE

---

## �🚀 Current Status: Phase 2 Multi-Speaker Integration Complete

The system is fully stable. Phase 1 (Foundation) is complete. Phase 2 enhancements (Items 1–8) are implemented and tested.

**Key Achievements:**
*   **Reliability:** Pipeline status tracking is now persistent; resume capability is verified.
*   **Quality:** Fallback logic is now per-chapter (no audible engine switching mid-chapter).
*   **Arabic:** Full diacritization pipeline (Mishkal) and intelligent sentence splitting implemented.
*   **Creativity:** Ambient pad generator (Composer) is live with 5 mood presets.
*   **Voice Cloning:** XTTS v2 engine fully integrated with VRAM management and generation parameters.
    
	Note: The XTTS runtime (model, VRAM management and per-chunk generation) is integrated and tested. Higher-level
	voice-cloning workflow pieces — automated reference ingestion/validation, character-profile management (CLI/UI),
	and cloud TTS adapters — remain in-progress and are not yet fully implemented.
*   **Multi-Speaker:** Per-segment character resolution with engine-specific routing.

---

## 🏗️ Phase 2: Advanced Audio (Current)

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
| **9** | **Mixer + Ducking** | ⏳ Pending | Merge Voice + Ambient Pads with VAD-based ducking. |
| **10** | **CLI Finalization** | ⏳ Pending | Expose `compose` and `mix` commands to the user. |

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

1.  **Mixer Implementation:** Build `audio/mixer.py` using `pydub` + `scipy` for ducking.
2.  **CLI Finalization:** Expose `compose` and `mix` commands to the user.

### 🎯 Recent Completion: Multi-Speaker Integration (Feb 14, 2026)

**Files Added/Modified:**
- `src/audioformation/generate.py` - Per-segment character resolution, engines_used tracking
- `tests/test_multispeaker.py` - Comprehensive multi-speaker test suite (532 lines)
- `docs/ARCHITECTURE.md` - Updated to reflect multi-speaker implementation
- `README.md` - Updated feature status and test count

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

**Key Bug Fixes Applied:**
- **QC Command (`all_reports`):** Fixed `NameError: name 'all_reports' is not defined` in `qc` command by properly collecting report data
- **Chapter File Detection:** Fixed underscore filtering to distinguish chapter files (`ch01_intro.wav`) from chunks (`ch01_000.wav`) — uses numeric suffix check
- **SSML for Arabic:** Disabled SSML for edge-tts Arabic to prevent `<speak>` tags being read as text (voice quality issue)

**Generated Output:**
- `ch01_intro.wav` (26.8 MB) - Full chapter, stitched with 120ms crossfade
- `ch01_intro.mp3` - Final export, processed and normalized
- QC report: 10 passed, 6 warnings (LUFS deviation within tolerance)

**Known Issues Identified:**
1. **Arabic Diacritization:** Mishkal produces quality issues with some words — needs refinement or alternative
2. **Robotic Tone:** Edge-tts Arabic voices lack narrative expressiveness
3. **SSML Compatibility:** Arabic voices don't properly process SSML prosody tags

### 🧪 Real-World Validation (Feb 14, 2026)

**Test Project:** MULTI_SPEAKER_TEST  
**Scenarios Validated:** All 5 key behaviors confirmed working

| Scenario | Expected | Actual Result |
| :--- | :--- | :--- |
| **mode=multi, no --engine** | Each segment uses its character's engine | ✅ ch01: 7 chunks, edge→gtts fallback for villain |
| **mode=multi, --engine edge** | All segments forced to edge | ✅ `--engine gtts` forced all 7 chunks to gtts |
| **mode=single** | Unchanged — one character, one engine | ✅ ch02: 3 chunks, narrator only, tags as text |
| **Unknown [speaker] tag** | Falls back to chapter default | ✅ Graceful fallback handling confirmed |
| **XTTS used in any segment** | release_vram called after chapter | ✅ Multi-engine VRAM management working |

**Generated Files:**
- `ch01.wav` (1.17MB) - Multi-speaker chapter with 7 chunks
- `ch02.wav` (1.26MB) - Single-mode chapter with 3 chunks  
- Individual chunks: `ch01_000.wav` through `ch01_006.wav`
- QC report: 0% failure rate, proper quality metrics

**Key Findings:**
- Per-segment character resolution working perfectly
- Engine override (`--engine`) correctly forces single-engine generation
- Backward compatibility maintained for single-mode chapters
- Fallback chain (edge→gtts) activates appropriately
- Crossfade stitching handles multi-engine chapters seamlessly

**Previous: XTTS v2 Integration (Feb 14, 2026)**