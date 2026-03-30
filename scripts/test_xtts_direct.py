import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path("e:/co/Audio-Formation/src")))

from audioformation.engines.xtts import XTTSEngine
from audioformation.engines.base import GenerationRequest


async def test():
    print("Initializing XTTS Engine...")
    try:
        e = XTTSEngine(device="cpu")
        # Reference audio (Ahmed)
        ref = Path(
            "e:/co/Audio-Formation/PROJECTS/GOLDEN-REEL-S1/02_VOICES/references/ahmed_clean_ref.wav"
        )
        print(f"Using reference: {ref} (Exists: {ref.exists()})")

        req = GenerationRequest(
            text="His consciousness returned slowly. Like a loading screen — vision first, then spatial awareness, then something resembling borders.",
            output_path=Path("test_xtts.wav"),
            language="en",
            reference_audio=ref,
            params={"temperature": 0.7, "repetition_penalty": 5.0},
        )

        print("Starting generation...")
        res = await e.generate(req)

        if res.success:
            print(f"SUCCESS: Generated {res.output_path} ({res.duration_sec:.1f}s)")
        else:
            print(f"FAILURE: {res.error}")

    except Exception as exc:
        print(f"EXCEPTION: {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())
