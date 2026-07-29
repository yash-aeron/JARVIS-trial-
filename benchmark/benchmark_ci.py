"""
benchmark_ci.py — CI-safe benchmark runner with threshold assertions.

Runs all latency benchmarks and exits non-zero if any metric exceeds its
defined SLA budget.  Called directly by the GitHub Actions CI workflow.
"""
import asyncio
import sys
import os

# Ensure project root is on sys.path when invoked as `python benchmark/benchmark_ci.py`
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from benchmark.benchmarking import SystemBenchmarking

# ── SLA thresholds (milliseconds) ─────────────────────────────────────────────
THRESHOLDS = {
    "startup_time_ms":           500.0,
    "planner_latency_ms":         50.0,
    "executor_latency_ms":       150.0,
    "event_bus_latency_ms":       25.0,
    "memory_retrieval_latency_ms": 50.0,
    "tool_execution_latency_ms":  100.0,
}

PASS  = "[PASS]"
FAIL  = "[FAIL]"
RESET = ""

async def main() -> int:
    suite   = SystemBenchmarking()
    results = await suite.run_all_benchmarks()
    data    = results.model_dump()

    print("\n" + "=" * 62)
    print("  JARVIS CI Benchmark Suite — Latency Threshold Report")
    print("=" * 62)
    print(f"  {'Metric':<40} {'Value':>10}   {'SLA':>10}   Status")
    print("-" * 62)

    any_failure = False
    for key, sla in THRESHOLDS.items():
        value  = data.get(key, 0.0)
        passed = value <= sla
        status = PASS if passed else FAIL
        if not passed:
            any_failure = True
        print(f"  {key:<40} {value:>9.3f}ms  {sla:>9.1f}ms   {status}")

    print("=" * 62)
    if any_failure:
        print("  FAILED: One or more latency thresholds exceeded.\n")
        return 1
    else:
        print("  PASSED: All latency thresholds within SLA.\n")
        return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
