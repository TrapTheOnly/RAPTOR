from typing import Any, Dict, Optional

from flask import request


def parse_json_object() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def normalize_password_hash(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    try:
        return bytes(value)
    except Exception:
        return None


def normalize_auth_key(username: Any) -> str:
    return str(username or "").strip().lower()
