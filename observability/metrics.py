import time
from typing import Dict, Any, List

class MetricsCollector:
    """Tracks latency, throughput, execution counts, and memory speeds."""
    
    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}

    def increment(self, metric_name: str, value: int = 1) -> None:
        self._counters[metric_name] = self._counters.get(metric_name, 0) + value

    def record_latency(self, metric_name: str, duration_sec: float) -> None:
        if metric_name not in self._latencies:
            self._latencies[metric_name] = []
        self._latencies[metric_name].append(duration_sec)

    def get_summary(self) -> Dict[str, Any]:
        summary = {"counters": self._counters, "avg_latencies_ms": {}}
        for name, values in self._latencies.items():
            if values:
                summary["avg_latencies_ms"][name] = round((sum(values) / len(values)) * 1000, 2)
        return summary

metrics = MetricsCollector()
