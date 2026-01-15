import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    log_dir = "/opt/webapp/logs"
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "webapp.log")

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # ------------------------------
    # Console Handler
    # ------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(module)s: %(message)s"
    )
    console_handler.setFormatter(console_format)

    # ------------------------------
    # Rotating File Handler
    # ------------------------------
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(module)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)

    # ------------------------------
    # Apply handlers only once
    # ------------------------------
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
