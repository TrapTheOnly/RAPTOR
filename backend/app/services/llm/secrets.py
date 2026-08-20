"""Fernet helpers for llm_connections.config secret fields."""

from typing import Any, Dict, Iterable, Mapping, Optional

from app.services.ingest.secrets import (
    MASK,
    decrypt_value,
    encrypt_value,
    parse_source_config,
)

SECRET_CONFIG_FIELDS = (
    "api_key",
    "aws_bearer_token",
    "aws_secret_access_key",
    "aws_session_token",
)


def encrypt_config(
    config: Mapping[str, Any],
    *,
    secret_fields: Iterable[str] = SECRET_CONFIG_FIELDS,
) -> Dict[str, Any]:
    out = dict(config or {})
    for field in secret_fields:
        if field in out and out[field] not in (None, "", MASK):
            out[field] = encrypt_value(str(out[field]))
        elif out.get(field) == MASK:
            out.pop(field, None)
    return out


def decrypt_config(
    config: Mapping[str, Any],
    *,
    secret_fields: Iterable[str] = SECRET_CONFIG_FIELDS,
) -> Dict[str, Any]:
    out = dict(config or {})
    for field in secret_fields:
        if out.get(field):
            out[field] = decrypt_value(str(out[field]))
    return out


def mask_config(
    config: Mapping[str, Any],
    *,
    secret_fields: Iterable[str] = SECRET_CONFIG_FIELDS,
) -> Dict[str, Any]:
    out = dict(config or {})
    for field in secret_fields:
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
    return encrypt_config(merged, secret_fields=secret_fields)


__all__ = [
    "MASK",
    "SECRET_CONFIG_FIELDS",
    "decrypt_config",
    "encrypt_config",
    "mask_config",
    "merge_config",
    "parse_source_config",
]
