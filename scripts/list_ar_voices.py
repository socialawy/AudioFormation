import asyncio
import edge_tts


async def main():
    voices = await edge_tts.list_voices()
    ar_voices = [v["ShortName"] for v in voices if v["Locale"].startswith("ar")]
    print("\n".join(ar_voices))


if __name__ == "__main__":
    asyncio.run(main())
