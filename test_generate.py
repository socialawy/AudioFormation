from audioformation.generate import generate_project
import asyncio

async def test():
    try:
        result = await generate_project(
            project_id="V03",
            engine_name="edge",
            chapters=["ch01_intro"]
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
