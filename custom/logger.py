import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys


LOGGER_NAME = "pipeline"

# Create a global logger
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.DEBUG)  # Global default level

# Log format
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Prevent duplicate handlers if already added (e.g. on reload)
if not logger.handlers:
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rolling file handler
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, LOGGER_NAME + ".log")

    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        utc=False  # set True if you prefer UTC cutover
    )

    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
