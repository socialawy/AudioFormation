import asyncio
import edge_tts


async def list_voices():
    voices = await edge_tts.VoicesManager.create()
    all_v = voices.voices
    print(f"Total voices: {len(all_v)}")

    ar = [v for v in all_v if "ar-" in v["Locale"]]
    en = [v for v in all_v if "en-" in v["Locale"]]

    print("\nARABIC:")
    for v in ar:
        print(f"{v['ShortName']} | {v['Gender']}")

    print("\nENGLISH (Top 40):")
    for v in en[:40]:
        print(f"{v['ShortName']} | {v['Gender']}")


if __name__ == "__main__":
    asyncio.run(list_voices())
