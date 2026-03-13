from functools import wraps
from typing import Callable

from flask import g, jsonify, request

from app.services.service_api_service import authenticate_service_api_key


def _extract_api_key_from_request() -> str:
    header_key = str(request.headers.get("X-API-Key") or "").strip()
    if header_key:
        return header_key

    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def service_api_key_required(scope: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapped(*args, **kwargs):
            api_key = _extract_api_key_from_request()
            payload, status_code = authenticate_service_api_key(api_key, scope)
            if status_code != 200:
                return jsonify(payload), status_code
            g.service_account = payload.get("service_account") or {}
            return func(*args, **kwargs)

        return wrapped

    return decorator


__all__ = ["service_api_key_required"]
