import logging
import os
from pathlib import Path
from .config import DB_PATH


def configure_logging():
    """
    Configure application-wide logging with both file and console handlers.
    Ensures the log directory exists.
    """
    log_folder = Path(DB_PATH).parent
    log_folder.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_folder, "application.log"), mode="w"),
            logging.StreamHandler(),
        ],
    )

    return logging.getLogger(__name__)
