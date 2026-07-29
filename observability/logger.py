import logging
import time
import sys
from typing import Optional

class StructuredFormatter(logging.Formatter):
    """Production Structured Formatter formatting log output with timestamps, log levels, subsystem names, correlation IDs, and execution timing."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname
        subsystem = getattr(record, "subsystem", "JARVIS")
        correlation_id = getattr(record, "correlation_id", "-")
        elapsed_ms = getattr(record, "elapsed_ms", None)
        
        timing_str = f" ({elapsed_ms:.2f}ms)" if elapsed_ms is not None else ""
        return f"[{timestamp}] [{level}] [{subsystem}] [CID: {correlation_id}]{timing_str}: {record.getMessage()}"

def setup_logger(name: str = "JARVIS") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()

class TimerLogger:
    """Context manager for automatic timing logging of operations."""
    def __init__(self, operation_name: str, correlation_id: Optional[str] = None):
        self.operation_name = operation_name
        self.correlation_id = correlation_id
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"Started operation: '{self.operation_name}'", extra={"correlation_id": self.correlation_id or "-"})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000.0
        status = "failed" if exc_type else "completed"
        logger.info(f"Finished operation: '{self.operation_name}' [{status}]", extra={"correlation_id": self.correlation_id or "-", "elapsed_ms": elapsed_ms})
