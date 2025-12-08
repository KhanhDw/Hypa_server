import logging
import logging.handlers
import os
from datetime import datetime

def setup_logging():
    """
    Set up logging configuration to write logs to files with date-time names
    """
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create log file name with current date and time
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = os.path.join(logs_dir, f"app_{current_time}.log")
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create file handler
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Create console handler (optional - can be removed if only file logging is needed)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Also configure uvicorn access logs to use the same format
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addHandler(file_handler)
    access_logger.setLevel(logging.INFO)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name
    """
    return logging.getLogger(name)