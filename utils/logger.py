import logging
import os
import sys
from typing import Optional

_logger_instance: Optional[logging.Logger] = None


def get_logger(name: str = "codemind") -> logging.Logger:
    """
    Get or create a singleton logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    global _logger_instance

    if _logger_instance is not None:
        return _logger_instance

    # Create new logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        _logger_instance = logger
        return logger

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG level)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(
        os.path.join(log_dir, "app.log"),
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False

    _logger_instance = logger
    return logger
