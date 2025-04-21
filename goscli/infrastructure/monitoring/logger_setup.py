"""Centralized logging configuration for the gosCLI application.

Sets up standard Python logging with appropriate levels, formatters,
and handlers (e.g., console, file).
"""

import logging
import sys
from typing import Optional

# TODO: Make log level and file configurable via settings
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_FILE = None # Or e.g., Path.home() / ".goscli_cache" / "goscli.log"

def setup_logging(
    log_level: int = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: Optional[str] = DEFAULT_LOG_FILE
) -> None:
    """Configures the root logger for the application.

    Args:
        log_level: The minimum logging level (e.g., logging.DEBUG, logging.INFO).
        log_format: The format string for log messages.
        log_file: Optional path to a file for logging output.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers attached to the root logger
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Create Console Handler
    console_handler = logging.StreamHandler(sys.stdout) # Use stdout for console
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Create File Handler (Optional)
    if log_file:
        try:
            # TODO: Add file rotation (e.g., RotatingFileHandler)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            logging.info(f"Logging to file: {log_file}")
        except Exception as e:
            logging.error(f"Failed to set up file logging to {log_file}: {e}", exc_info=True)
    
    logging.info(f"Logging configured. Level={logging.getLevelName(log_level)}")

# Example of how to call this early in the application (e.g., in main.py)
# if __name__ == "__main__":
#     setup_logging()
#     # ... rest of the application startup 