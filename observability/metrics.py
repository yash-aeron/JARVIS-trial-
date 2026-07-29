import time
from typing import Dict, Any, List, Optional
from core.models import SystemStatusModel, BenchmarkResultModel
from system.monitor import SystemMonitor
from observability.logger import logger

class MetricsProvider:
    """Unified Metrics Provider consolidating system status monitors, benchmarking latencies, and execution counters across Dashboard, Evaluators, and Tests."""
    
    def __init__(self, system_monitor: Optional[SystemMonitor] = None):
        self.system_monitor = system_monitor or SystemMonitor()
        self._latencies_ms: Dict[str, List[float]] = {
            "event_bus": [],
            "memory_retrieval": [],
            "tool_execution": []
        }
        self._execution_counts: Dict[str, int] = {
            "commands_processed": 0,
            "tools_executed": 0,
            "plans_created": 0
        }

    def record_latency(self, metric_name: str, latency_ms: float) -> None:
        if metric_name not in self._latencies_ms:
            self._latencies_ms[metric_name] = []
        self._latencies_ms[metric_name].append(latency_ms)
        if len(self._latencies_ms[metric_name]) > 100:
            self._latencies_ms[metric_name].pop(0)

    def increment_counter(self, metric_name: str, value: int = 1) -> None:
        self._execution_counts[metric_name] = self._execution_counts.get(metric_name, 0) + value

    def get_system_status(self) -> SystemStatusModel:
        return self.system_monitor.get_stats()

    def get_benchmark_results(self) -> BenchmarkResultModel:
        avg_event = (sum(self._latencies_ms["event_bus"]) / len(self._latencies_ms["event_bus"])) if self._latencies_ms["event_bus"] else 15.0
        avg_mem = (sum(self._latencies_ms["memory_retrieval"]) / len(self._latencies_ms["memory_retrieval"])) if self._latencies_ms["memory_retrieval"] else 15.0
        avg_tool = (sum(self._latencies_ms["tool_execution"]) / len(self._latencies_ms["tool_execution"])) if self._latencies_ms["tool_execution"] else 15.0
        
        return BenchmarkResultModel(
            event_bus_latency_ms=round(avg_event, 3),
            memory_retrieval_latency_ms=round(avg_mem, 3),
            tool_execution_latency_ms=round(avg_tool, 3)
        )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "system_status": self.get_system_status().model_dump(),
            "benchmarks": self.get_benchmark_results().model_dump(),
            "counters": self._execution_counts
        }
