import logging
import time
from typing import Any, Dict

from app.config import (
    DB_PATH,
    FAILED_LOGIN_ATTEMPT_LIMIT,
    LOGIN_LOCKOUT_BASE_MINUTES,
    LOGIN_LOCKOUT_MAX_MINUTES,
)
from app.http.request_utils import normalize_auth_key
from app.integrations.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def get_login_lockout_status(username: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    key = normalize_auth_key(username)
    if not key:
        return {
            "locked": False,
            "retry_after_seconds": 0,
            "remaining_attempts": FAILED_LOGIN_ATTEMPT_LIMIT,
        }

    now_epoch = int(time.time())
    try:
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT failed_attempts, lockout_until_epoch
                FROM auth_lockouts
                WHERE username = ?
                """,
                (key,),
            )
            row = c.fetchone()
            if not row:
                return {
                    "locked": False,
                    "retry_after_seconds": 0,
                    "remaining_attempts": FAILED_LOGIN_ATTEMPT_LIMIT,
                }

            failed_attempts = max(0, int(row[0] or 0))
            lockout_until_epoch = max(0, int(row[1] or 0))
            retry_after_seconds = max(0, lockout_until_epoch - now_epoch)
            return {
                "locked": retry_after_seconds > 0,
                "retry_after_seconds": retry_after_seconds,
                "remaining_attempts": max(0, FAILED_LOGIN_ATTEMPT_LIMIT - failed_attempts),
            }
    except Exception as e:
        logger.error(f"Error reading login lockout state for '{key}': {e}")
        return {
            "locked": False,
            "retry_after_seconds": 0,
            "remaining_attempts": FAILED_LOGIN_ATTEMPT_LIMIT,
        }


def register_failed_login_attempt(username: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    key = normalize_auth_key(username)
    if not key:
        return {"locked": False, "retry_after_seconds": 0}

    now_epoch = int(time.time())
    try:
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT failed_attempts, lockout_level, lockout_until_epoch
                FROM auth_lockouts
                WHERE username = ?
                """,
                (key,),
            )
            row = c.fetchone()
            failed_attempts = max(0, int(row[0] or 0)) if row else 0
            lockout_level = max(0, int(row[1] or 0)) if row else 0
            lockout_until_epoch = max(0, int(row[2] or 0)) if row else 0

            if lockout_until_epoch > now_epoch:
                return {
                    "locked": True,
                    "retry_after_seconds": lockout_until_epoch - now_epoch,
                }

            failed_attempts += 1
            lockout_triggered = False
            retry_after_seconds = 0

            if failed_attempts >= FAILED_LOGIN_ATTEMPT_LIMIT:
                computed_minutes = LOGIN_LOCKOUT_BASE_MINUTES * (2 ** lockout_level)
                lockout_minutes = (
                    min(LOGIN_LOCKOUT_MAX_MINUTES, computed_minutes)
                    if LOGIN_LOCKOUT_MAX_MINUTES > 0
                    else computed_minutes
                )
                retry_after_seconds = int(lockout_minutes * 60)
                lockout_until_epoch = now_epoch + retry_after_seconds
                lockout_level += 1
                failed_attempts = 0
                lockout_triggered = True

            if row:
                c.execute(
                    """
                    UPDATE auth_lockouts
                    SET failed_attempts = ?,
                        lockout_level = ?,
                        lockout_until_epoch = ?,
                        updated_at = NOW()
                    WHERE username = ?
                    """,
                    (failed_attempts, lockout_level, lockout_until_epoch, key),
                )
            else:
                c.execute(
                    """
                    INSERT INTO auth_lockouts (
                        username, failed_attempts, lockout_level, lockout_until_epoch, updated_at
                    ) VALUES (?, ?, ?, ?, NOW())
                    """,
                    (key, failed_attempts, lockout_level, lockout_until_epoch),
                )
            conn.commit()

            return {
                "locked": lockout_triggered,
                "retry_after_seconds": retry_after_seconds,
                "remaining_attempts": max(0, FAILED_LOGIN_ATTEMPT_LIMIT - failed_attempts),
            }
    except Exception as e:
        logger.error(f"Error storing failed login attempt for '{key}': {e}")
        return {"locked": False, "retry_after_seconds": 0}


def clear_login_lockout_state(username: str, db_path: str = DB_PATH) -> None:
    key = normalize_auth_key(username)
    if not key:
        return

    try:
        with get_db_connection(db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM auth_lockouts WHERE username = ?", (key,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error clearing login lockout state for '{key}': {e}")
