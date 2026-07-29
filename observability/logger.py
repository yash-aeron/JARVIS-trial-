import logging
import sys
from pathlib import Path
from typing import Optional

def setup_logger(name: str = "JARVIS", log_file: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s')
        
        # Console Handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File Handler (optional)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(formatter)
            logger.addHandler(fh)
            
    return logger

logger = setup_logger()
