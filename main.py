import sys
import argparse
import asyncio
from core.app import JARVISApp
from dashboard.app import run_dashboard
from benchmark.benchmarking import SystemBenchmarking
from evaluation.evaluator import QualityEvaluator
from observability.logger import logger

async def run_cli_loop(app: JARVISApp):
    await app.initialize()
    print("\n" + "="*60)
    print("  JARVIS AI Operating System Assistant v1.0 [CLI Mode]")
    print("  Type 'exit' or 'quit' to terminate.")
    print("="*60 + "\n")
    
    try:
        while True:
            cmd = input("JARVIS > ").strip()
            if not cmd:
                continue
            if cmd.lower() in ["exit", "quit"]:
                break
                
            res = await app.process_user_command(cmd)
            print(f"\n[JARVIS Response]: {res.response}")
            print(f"[Details]: Intent={res.intent}, Steps Executed={len(res.execution_results)}\n")
    finally:
        await app.shutdown()

async def run_benchmarks():
    suite = SystemBenchmarking()
    results = await suite.run_all_benchmarks()
    print("\n" + "="*50)
    print("  JARVIS Benchmarking Suite Results")
    print("="*50)
    for k, v in results.model_dump().items():
        print(f"  - {k}: {v}")
    print("="*50 + "\n")

def run_evaluations():
    evaluator = QualityEvaluator()
    res1 = evaluator.evaluate_tool_selection("app_launcher", "app_launcher")
    res2 = evaluator.evaluate_plan_optimality(2, 3)
    print("\n" + "="*50)
    print("  JARVIS Quality Evaluation Results")
    print("="*50)
    print(f"  - Tool Selection Accuracy: {100.0 if res1.match else 0.0}%")
    print(f"  - Plan Optimality Score: {100.0 if res2.optimal else 0.0}%")
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="JARVIS AI Operating System Assistant Bootloader")
    parser.add_argument("--cli", action="store_true", help="Launch JARVIS in interactive CLI mode")
    parser.add_argument("--gui", action="store_true", help="Launch PySide6 Desktop GUI Dashboard")
    parser.add_argument("--benchmark", action="store_true", help="Run system benchmarking suite")
    parser.add_argument("--eval", action="store_true", help="Run automated quality evaluation suite")
    
    args = parser.parse_args()
    
    if args.benchmark:
        asyncio.run(run_benchmarks())
    elif args.eval:
        run_evaluations()
    elif args.gui:
        app = JARVISApp()
        asyncio.run(app.initialize())
        run_dashboard(app.state_manager, app.event_bus)
    else:
        # Default to CLI mode if no flag is provided
        app = JARVISApp()
        asyncio.run(run_cli_loop(app))

if __name__ == "__main__":
    main()
