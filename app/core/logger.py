from loguru import logger
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOGS_LEVELS = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]

os.makedirs(LOG_DIR, exist_ok=True)

for level in LOGS_LEVELS:
    logger.add(
        os.path.join(LOG_DIR, f"{level.lower()}.log"),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file} | {message}",
        level=level,
        rotation="1024 MB",
        retention="7 days",
        compression="zip",
        enqueue=True,
        filter=lambda record, lvl=level: record["level"].name == lvl
    )
