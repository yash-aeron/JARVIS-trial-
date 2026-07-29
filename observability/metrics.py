import time
from typing import Dict, Any, List
from observability.logger import logger

class MetricsCollector:
    """Metrics Collector tracking subsystem execution latencies and system performance metrics."""
    
    def __init__(self):
        self._latencies: Dict[str, List[float]] = {
            "planner_latency_ms": [],
            "tool_latency_ms": [],
            "memory_retrieval_latency_ms": [],
            "speech_latency_ms": [],
            "event_bus_latency_ms": []
        }

    def record_latency(self, metric_name: str, duration_ms: float) -> None:
        if metric_name not in self._latencies:
            self._latencies[metric_name] = []
        self._latencies[metric_name].append(duration_ms)

    def get_summary(self) -> Dict[str, float]:
        summary = {}
        for k, v in self._latencies.items():
            summary[k] = round(sum(v) / len(v), 3) if v else 0.0
        return summary
