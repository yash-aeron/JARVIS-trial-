import asyncio
import traceback
from core.app import JARVISApp

async def main():
    try:
        app = JARVISApp()
        await app.initialize()
        
        print("\n--- Executing Real End-to-End Vertical Slice ---")
        res = await app.process_user_command("Open notepad")
        print("\n--- Result Summary ---")
        print(f"Correlation ID: {res['correlation_id']}")
        print(f"Intent: {res['intent']}")
        print(f"Response: {res['response']}")
        print(f"Execution Results: {res['execution_results']}\n")
        
        await app.shutdown()
    except Exception as e:
        print("EXCEPTION CAUGHT IN TEST SLICE:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
