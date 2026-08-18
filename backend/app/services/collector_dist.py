"""Packaged collector binaries served from the RAPTOR admin page."""

import os
from pathlib import Path

from app.config import BASE_DIR

COLLECTOR_VERSION = "1.1.0"

_ARTIFACTS = {
    "linux-amd64": "raptor-collector-linux-amd64",
    "linux-arm64": "raptor-collector-linux-arm64",
    "windows-amd64.exe": "raptor-collector-windows-amd64.exe",
    "windows-amd64": "raptor-collector-windows-amd64.exe",
}


def dist_dir() -> Path:
    configured = str(os.getenv("COLLECTOR_DIST_DIR") or "").strip()
    if configured:
        return Path(configured)
    return Path(BASE_DIR).resolve().parent / "collector" / "dist"


def artifact_path(name: str) -> Path | None:
    filename = _ARTIFACTS.get(str(name or "").strip())
    if not filename:
        return None
    path = dist_dir() / filename
    return path if path.is_file() else None


def available_downloads() -> dict:
    items = {}
    for key, filename in _ARTIFACTS.items():
        if key == "windows-amd64":
            continue
        path = dist_dir() / filename
        items[key] = {
            "filename": filename,
            "available": path.is_file(),
            "size": path.stat().st_size if path.is_file() else 0,
        }
    return items


def version_payload() -> dict:
    return {
        "version": COLLECTOR_VERSION,
        "downloads": available_downloads(),
    }
