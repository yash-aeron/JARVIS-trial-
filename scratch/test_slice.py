import asyncio
from core.app import JARVISApp

async def main():
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

if __name__ == "__main__":
    asyncio.run(main())
