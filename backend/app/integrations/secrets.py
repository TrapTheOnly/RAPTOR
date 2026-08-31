import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    raw = hashlib.sha256((os.getenv("SECRET_KEY") or "your_secret_key").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt_secret(plaintext: str) -> str:
    value = str(plaintext or "")
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: Optional[str]) -> str:
    value = str(token or "").strip()
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Could not decrypt the stored integration secret.") from exc


def has_secret(token: Optional[str]) -> bool:
    return bool(str(token or "").strip())
