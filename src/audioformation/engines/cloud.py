"""
Cloud TTS engine adapters — ElevenLabs and OpenAI.

TODO(Phase 2): Implement cloud engine adapters
  - [ ] ElevenLabsEngine class
      - [ ] Voice selection (premade + custom voices)
      - [ ] SSML support (limited, check docs)
      - [ ] Streaming generation for long texts
      - [ ] API key from 00_CONFIG/engines.json
      - [ ] Rate limiting (10 req/min free tier)
  - [ ] OpenAIEngine class
      - [ ] GPT-4o voice models (alloy, echo, fable, etc.)
      - [ ] Speed control (0.25x - 4.0x)
      - [ ] Response format (mp3, opus, aac, flac)
      - [ ] API key from environment or config
  - [ ] Shared cloud utilities
      - [ ] Retry with exponential backoff
      - [ ] Quota tracking per engine
      - [ ] Fallback to local engines on failure
"""

# Placeholder for Phase 2 implementation
