# AudioBook Production Standards (Doxascope Pilot)

These guidelines establish the process for converting Doxascope Universe chapters (from Markdown/Maktaba) into AudioFormation-ready text files for TTS generation.

## 1. File Formatting & Conversion (CRITICAL FOR AI AGENTS)
- **Source**: Doxascope EXPERIENCE Markdown files (`public/content/novel/`).
- **Target**: AudioFormation `01_TEXT/chapters/` plain text (`.txt`) files.
- **Encoding**: MUST be UTF-8 (specifically crucial for Arabic).
- **WARNING FOR AI AGENTS**: DO NOT use PowerShell output redirection (`>` or `Out-File`) to create these `.txt` files from `.md` sources. This will corrupt the UTF-8 encoding (Mojibake), causing TTS engines to read literal unicode character codes instead of words.
- **Correct Workflow**: Write a native Python script to extract and write the text strictly using `encoding='utf-8'`, OR rely on the user to manually save the text files. Once valid UTF-8 files exist, use `audioformation ingest [PROJECT_ID] --source [DIR]` to let Node 1 natively handle ingestion.
- **Cleanup**: Remove Markdown metadata, frontmatter (like `> **الحالة:** ✅ مكتمل`), and heading titles (unless meant to be read aloud).

## 2. Text Content & Chunking Rules
- **Formatting Elements**:
    - **Italics/Bold**: `*text*` or `**text**` denoting internal thoughts or vocal emphasis should be left intact if the TTS engine maps them to SSML emphasis, or replaced with specific voice character tags if indicating a different speaker. For Edge-TTS, remove asterisks or convert them to SSML pauses (`...` or `—`) if they indicate breaks.
    - **Paragraphs**: Keep natural paragraph breaks (double newline). AudioFormation's `breath_group` chunking strategy will use them.

## 3. Multi-Speaker Tagging (Phase 2 Feature)
- Standard novel text implicitly uses the `narrator` voice.
- For internal monologues or specific characters, wrap segments in `[character_id]` tags on a new line.
    - *Example:*
      ````text
      [narrator]
      نظر إلى السماء وقال بصوت خافت.
      
      [hero]
      لا يوجد مفر.
      ````
- If it's a single-narrator audiobook (like this Pilot), do not add speaker tags; use the `direction` field in `project.json` to guide the narrator's emotion/pace.

## 4. Arabic Specifics
- **Diacritics (التشكيل)**: AudioFormation auto-diacritizes if < 5% using Mishkal. For best quality (especially in philosophical texts like Doxascope), pre-diacritize ambiguous words manually or ensure the script is rich enough.
- **Bilingual Mix**: Auto-detected by AudioFormation. Keep English words (like "Coherence" or "Pattern" if retained in AR text) isolated so the pipeline tags them `[en]` correctly.

## 5. QC Guidelines & Export
- Check `03_GENERATED/compare/` for voice testing before running full chapters.
- Ensure `project.json` `qc` criteria are set (SNR > 20dB, max deviation 30%).
- Target LUFS: -16.0 for the final audiobook mix (`M4B` output).
