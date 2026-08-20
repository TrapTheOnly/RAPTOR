"""Fernet helpers for dns_sources.config secret fields."""

import base64
import hashlib
import json
import os
from typing import Any, Dict, Iterable, Mapping, Optional

from cryptography.fernet import Fernet, InvalidToken

SECRET_CONFIG_FIELDS = (
    "api_token",
    "aws_secret_access_key",
    "access_key_secret",
    "client_secret",
    "service_account_json",
    "private_key",
)
MASK = "••••••••"
_PREFIX = "enc:"


def _fernet() -> Fernet:
    raw = str(os.getenv("SECRET_KEY") or "your_secret_key").encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(value: str) -> str:
    text = str(value or "")
    if not text or text.startswith(_PREFIX):
        return text
    token = _fernet().encrypt(text.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_value(value: str) -> str:
    text = str(value or "")
    if not text.startswith(_PREFIX):
        return text
    token = text[len(_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def parse_source_config(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(loaded, dict):
            return loaded
    return {}


def encrypt_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(config or {})
    for field in SECRET_CONFIG_FIELDS:
        if field in out and out[field] not in (None, "", MASK):
            out[field] = encrypt_value(str(out[field]))
        elif out.get(field) == MASK:
            out.pop(field, None)
    return out


def decrypt_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(config or {})
    for field in SECRET_CONFIG_FIELDS:
        if field in out and out[field]:
            out[field] = decrypt_value(str(out[field]))
    return out


def mask_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(config or {})
    for field in SECRET_CONFIG_FIELDS:
        if out.get(field):
            out[field] = MASK
    return out


def merge_config(
    existing: Optional[Mapping[str, Any]],
    incoming: Optional[Mapping[str, Any]],
    *,
    secret_fields: Iterable[str] = SECRET_CONFIG_FIELDS,
) -> Dict[str, Any]:
    merged = dict(existing or {})
    for key, value in dict(incoming or {}).items():
        if key in secret_fields and value in (None, "", MASK):
            continue
        merged[key] = value
    return encrypt_config(merged)


__all__ = [
    "MASK",
    "SECRET_CONFIG_FIELDS",
    "decrypt_config",
    "decrypt_value",
    "encrypt_config",
    "encrypt_value",
    "mask_config",
    "merge_config",
    "parse_source_config",
]
