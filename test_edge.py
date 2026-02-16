import asyncio
from pathlib import Path
from audioformation.engines.edge_tts import EdgeTTSEngine
from audioformation.engines.base import GenerationRequest

async def test():
    engine = EdgeTTSEngine()
    
    # Test the path creation logic from generate.py
    raw_dir = Path("test_raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    chunk_id = "test_000"
    chunk_path = raw_dir / f"{chunk_id}.wav"
    
    print(f"chunk_path type: {type(chunk_path)}")
    print(f"chunk_path value: {chunk_path}")
    print(f"chunk_path.suffix: {chunk_path.suffix}")
    
    request = GenerationRequest(text='Hello test', output_path=chunk_path)
    result = await engine.generate(request)
    print(f'Success: {result.success}, error: {result.error}')

if __name__ == "__main__":
    asyncio.run(test())
