import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(logs_dir: Path) -> None:
    logger = logging.getLogger("wrench")
    logger.setLevel(logging.DEBUG if os.environ.get("WRENCH_DEV") == "1" else logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter(_FORMAT)
    file_handler = RotatingFileHandler(
        logs_dir / "wrench.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if os.environ.get("WRENCH_DEV") == "1":
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
