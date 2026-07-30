import time
import functools
import traceback
from typing import Dict, Any, List, Optional
from observability.logger import logger
from observability.metrics import metrics

class TraceSpan:
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        logger.debug(f"[Trace Start] {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        metrics.record_latency(self.operation_name, duration * 1000.0)
        if exc_type:
            logger.error(f"[Trace Fail] {self.operation_name} after {duration:.4f}s: {exc_val}")
        else:
            logger.debug(f"[Trace End] {self.operation_name} completed in {duration:.4f}s")

def trace(operation_name: Optional[str] = None):
    def decorator(func):
        op_name = operation_name or func.__qualname__
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with TraceSpan(op_name):
                return await func(*args, **kwargs)
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with TraceSpan(op_name):
                return func(*args, **kwargs)
            
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
