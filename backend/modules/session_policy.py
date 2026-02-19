"""Compatibility facade for session policy utilities."""

from app.services.session_policy_service import (
    SESSION_ACTIVE_TIMEOUT_SECONDS,
    SESSION_EXTENSION_SECONDS,
    SESSION_IDLE_TIMEOUT_SECONDS,
    SESSION_MAX_EXTENSION_SECONDS,
    extend_session,
    get_session_timing,
    initialize_session_tracking,
    session_has_expired,
)

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
