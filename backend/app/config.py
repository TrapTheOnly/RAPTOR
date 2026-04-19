import logging
import os
from typing import Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data"))
SHARED_PATH = os.getenv("SHARED_PATH", os.path.join(BASE_DIR, "shared"))
BACKUP_FOLDER = os.getenv("BACKUP_FOLDER", os.path.join(BASE_DIR, "backups"))
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
DB_PATH = DATABASE_URL  # Backward-compatible alias for existing call signatures.

FAILED_LOGIN_ATTEMPT_LIMIT = max(1, int(os.getenv("FAILED_LOGIN_ATTEMPT_LIMIT", "5")))
LOGIN_LOCKOUT_BASE_MINUTES = max(1, int(os.getenv("LOGIN_LOCKOUT_BASE_MINUTES", "1")))
LOGIN_LOCKOUT_MAX_MINUTES = max(0, int(os.getenv("LOGIN_LOCKOUT_MAX_MINUTES", "0")))


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def configure_logging(db_path: Optional[str] = None) -> None:
    target = str(db_path or "").strip()
    if target and not target.startswith(("postgres://", "postgresql://")):
        log_folder = os.path.dirname(target)
    else:
        log_folder = DATA_PATH
    os.makedirs(log_folder, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_folder, "application.log"), mode="w"),
            logging.StreamHandler(),
        ],
        force=True,
    )
