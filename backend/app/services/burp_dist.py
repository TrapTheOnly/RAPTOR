"""Packaged Burp Live JAR served from the wave page."""

import os
from pathlib import Path

from app.config import BASE_DIR

BURP_EXTENSION_VERSION = "1.1.1"
JAR_NAME = "raptor-burp.jar"


def dist_dir() -> Path:
    configured = str(os.getenv("BURP_DIST_DIR") or "").strip()
    if configured:
        return Path(configured)
    return Path(BASE_DIR).resolve().parent / "burp-extension" / "dist"


def jar_path() -> Path | None:
    path = dist_dir() / JAR_NAME
    return path if path.is_file() else None


def version_payload() -> dict:
    path = jar_path()
    return {
        "version": BURP_EXTENSION_VERSION,
        "filename": JAR_NAME,
        "available": bool(path),
        "size": path.stat().st_size if path else 0,
    }
