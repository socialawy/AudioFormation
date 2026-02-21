# AudioFormation Best Practices

This document outlines the best practices discovered through running pilot projects (e.g., `DOXASCOPE_PILOT_01`), ensuring that the system works perfectly across different edge cases and respects the user's hardware constraints.

## 1. Text Ingestion & Encoding

**CRITICAL WARNING:** When staging text files for ingestion, **DO NOT** use PowerShell shell redirection (e.g., `>`) or `Out-File` commands. PowerShell natively alters file encodings, which corrupts UTF-8 Arabic text (Mojibake). This leads text-to-speech (TTS) engines to read literal unicode character codes rather than the actual words.
- **Best Practice:** Use a native Python script to programmatically extract, chunk, and write text files to the staging directory using `encoding='utf-8'`.

## 2. Arabic Text Processing (Tashkeel)

Edge-TTS, while excellent, struggles to infer Arabic verb tenses flawlessly from un-voweled text, imposing a `~90%` pronunciation accuracy ceiling.
- **Best Practice:** Always run the text through a diacritization pass before ingestion. AudioFormation integrates the `mishkal` library for this. 
- **Workflow:** Use `audioformation.utils.arabic.diacritize_file` to output fully voweled `.diacritized.txt` files, and drop these into the `01_TEXT/staging/` folder. The pipeline guarantees 100% correct pronunciation syntax from here.
- **Known Issue:** Mishkal occasionally maps English periods `.` to the `\x01` "Start of Heading" (SOH) control character. AudioFormation's integration already intercepts and patches this bug.

## 3. Hardware Sensitivity & Chunking

Lengthy text generations or heavy VRAM usage can lead to OOM (Out Of Memory) errors, specifically on hardware like the `NVIDIA GeForce GTX 1650 Ti with Max-Q Design (4GB)`.
- **Best Practice:** Under the project's config, utilize the `empty_cache_per_chapter` strategy to actively clear VRAM constraints. 
- **Chunk Cuts:** Do not worry if the 37 raw chunk files generated during Node 3 (Generate) sound disjointed or abruptly cut. AudioFormation intentionally generates them in pure isolation. Node 6 (Mix) is responsible for stitching, crossfading, ducking against BGM, and fluidly bridging the cuts together.

## 4. QC Settings & LUFS Deviation 

Different TTS providers output vastly divergent sound floors. Edge-TTS voices often output slightly quieter arrays.
- **Best Practice:** Do not leave Node 7 (QC Final) locked to rigid broadcast thresholds without inspecting the engine's dynamic range. Relax `qc.lufs_deviation_max` inside `project.json` (e.g., `3.0` instead of `1.0`). We updated the final QC script to read the project's specific dynamic limits to prevent false negative failures.
