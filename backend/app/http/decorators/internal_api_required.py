import os
import secrets
from functools import wraps
from typing import Callable

from flask import jsonify, request


def internal_api_required(func: Callable) -> Callable:
    @wraps(func)
    def wrapped(*args, **kwargs):
        expected = str(os.getenv("RAPTOR_SERVICE_API_KEY") or "").strip()
        if not expected:
            return jsonify({"error": "Service not configured."}), 503

        header_key = str(request.headers.get("X-API-Key") or "").strip()
        if not header_key:
            auth = str(request.headers.get("Authorization") or "").strip()
            if auth.lower().startswith("bearer "):
                header_key = auth[7:].strip()

        if not header_key or not secrets.compare_digest(header_key, expected):
            return jsonify({"error": "Unauthorized access."}), 401

        return func(*args, **kwargs)

    return wrapped


__all__ = ["internal_api_required"]
