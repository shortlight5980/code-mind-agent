import logging
import os
import sys
from datetime import datetime
from typing import Optional

_logger_instances: dict[str, logging.Logger] = {}


def get_logger(name: str = "codemind") -> logging.Logger:
    """
    Get or create a singleton logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    if name in _logger_instances:
        return _logger_instances[name]

    # Create new logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        _logger_instances[name] = logger
        return logger

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (INFO level)
    stream = sys.stderr if os.getenv("CODEMIND_LOG_STDERR") == "1" else sys.stdout
    console_handler = logging.StreamHandler(stream)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (DEBUG level) - 按天命名
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 获取当前日期，格式：YYYY-MM-DD
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_filename = f"app_{today_str}.log"

    file_handler = logging.FileHandler(
        os.path.join(log_dir, log_filename),
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False

    _logger_instances[name] = logger
    return logger
