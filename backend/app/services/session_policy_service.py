import os
import time

from flask import session


def _parse_seconds(hours_env_name, seconds_env_name, default_hours):
    raw_seconds = os.getenv(seconds_env_name)
    if raw_seconds is not None:
        try:
            seconds = int(raw_seconds)
            if seconds > 0:
                return seconds
        except (TypeError, ValueError):
            pass

    raw_hours = os.getenv(hours_env_name)
    if raw_hours is not None:
        try:
            hours = float(raw_hours)
            if hours > 0:
                return int(hours * 3600)
        except (TypeError, ValueError):
            pass

    return int(default_hours * 3600)


SESSION_ACTIVE_TIMEOUT_SECONDS = _parse_seconds(
    "SESSION_ACTIVE_TIMEOUT_HOURS",
    "SESSION_ACTIVE_TIMEOUT_SECONDS",
    8,
)
SESSION_IDLE_TIMEOUT_SECONDS = _parse_seconds(
    "SESSION_IDLE_TIMEOUT_HOURS",
    "SESSION_IDLE_TIMEOUT_SECONDS",
    1,
)
SESSION_EXTENSION_SECONDS = _parse_seconds(
    "SESSION_EXTENSION_HOURS",
    "SESSION_EXTENSION_SECONDS",
    1,
)
SESSION_MAX_EXTENSION_SECONDS = _parse_seconds(
    "SESSION_MAX_EXTENSION_HOURS",
    "SESSION_MAX_EXTENSION_SECONDS",
    4,
)


def initialize_session_tracking():
    now_epoch = int(time.time())
    session["login_at_epoch"] = now_epoch
    session["last_activity_epoch"] = now_epoch
    session["active_extension_seconds"] = 0
    session["idle_extension_seconds"] = 0
    session.permanent = True


def _to_int(value, default_value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_value


def get_session_timing(update_activity=False):
    if not session.get("logged_in"):
        return None

    now_epoch = int(time.time())
    login_at = _to_int(session.get("login_at_epoch"), now_epoch)
    last_activity = _to_int(session.get("last_activity_epoch"), login_at)

    active_extension = max(0, _to_int(session.get("active_extension_seconds"), 0))
    idle_extension = max(0, _to_int(session.get("idle_extension_seconds"), 0))

    max_active_limit = SESSION_ACTIVE_TIMEOUT_SECONDS + active_extension
    idle_limit = SESSION_IDLE_TIMEOUT_SECONDS + idle_extension

    active_elapsed = now_epoch - login_at
    idle_elapsed = now_epoch - last_activity

    active_remaining = max(0, max_active_limit - active_elapsed)
    idle_remaining = max(0, idle_limit - idle_elapsed)
    expired = active_remaining <= 0 or idle_remaining <= 0

    session["login_at_epoch"] = login_at
    session["active_extension_seconds"] = active_extension
    session["idle_extension_seconds"] = idle_extension

    if update_activity and not expired:
        session["last_activity_epoch"] = now_epoch
        idle_remaining = idle_limit
    else:
        session["last_activity_epoch"] = last_activity

    return {
        "expired": expired,
        "active_remaining_seconds": active_remaining,
        "idle_remaining_seconds": idle_remaining,
        "remaining_seconds": min(active_remaining, idle_remaining),
    }


def extend_session(extra_seconds=SESSION_EXTENSION_SECONDS):
    if not session.get("logged_in"):
        return None

    now_epoch = int(time.time())
    extra = max(0, _to_int(extra_seconds, 0))
    current_active_extension = max(0, _to_int(session.get("active_extension_seconds"), 0))
    current_idle_extension = max(0, _to_int(session.get("idle_extension_seconds"), 0))

    extension_cap = max(0, SESSION_MAX_EXTENSION_SECONDS)
    remaining_active_budget = max(0, extension_cap - current_active_extension)
    remaining_idle_budget = max(0, extension_cap - current_idle_extension)
    grant = min(extra, remaining_active_budget, remaining_idle_budget)

    session["active_extension_seconds"] = current_active_extension + grant
    session["idle_extension_seconds"] = current_idle_extension + grant
    if grant > 0:
        session["last_activity_epoch"] = now_epoch
    return get_session_timing(update_activity=False)


def session_has_expired(update_activity=True):
    timing = get_session_timing(update_activity=update_activity)
    if timing is None:
        return False
    return bool(timing["expired"])


__all__ = [
    "SESSION_ACTIVE_TIMEOUT_SECONDS",
    "SESSION_EXTENSION_SECONDS",
    "SESSION_IDLE_TIMEOUT_SECONDS",
    "SESSION_MAX_EXTENSION_SECONDS",
    "extend_session",
    "get_session_timing",
    "initialize_session_tracking",
    "session_has_expired",
]
