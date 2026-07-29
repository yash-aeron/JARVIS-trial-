import logging
import sys
from typing import Optional

class StructuredFormatter(logging.Formatter):
    """Structured Log Formatter displaying timestamp, log level, subsystem, correlation ID, and message."""
    
    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, 'correlation_id', '-')
        subsystem = getattr(record, 'subsystem', 'JARVIS')
        
        timestamp = self.formatTime(record, self.datefmt)
        return f"[{timestamp}] [{record.levelname}] [{subsystem}] [CID: {correlation_id}]: {record.getMessage()}"

def setup_logger(name: str = "JARVIS", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()
