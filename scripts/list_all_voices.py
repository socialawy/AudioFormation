"""
Utility to list public Edge TTS voices.
Note: This script only processes public metadata and contains no sensitive data.
"""
import asyncio
import edge_tts


async def list_voices():
    # Load available voices
    voices = await edge_tts.VoicesManager.create()

    # Filter Arabic
    ar_voices = voices.find(Locale="ar")
    print("ARABIC VOICES:")
    for v in ar_voices:
        print(f"{v['ShortName']} ({v['Gender']}) - {v['Locale']}")

    # Filter English
    en_voices = voices.find(Locale="en")
    print("\nENGLISH VOICES:")
    for v in en_voices:
        # Limit to 20 for brevity unless we find really good ones
        print(f"{v['ShortName']} ({v['Gender']}) - {v['Locale']}")


if __name__ == "__main__":
    asyncio.run(list_voices())
