import json
import os
from typing import Any, Dict, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DOCS_ROOT = os.path.join(BASE_DIR, "docs")
DOCS_MANIFEST_PATH = os.path.join(DOCS_ROOT, "manifest.json")
DOCS_CONTENT_ROOT = os.path.join(DOCS_ROOT, "content")
ROLE_ORDER = ["user", "pentester", "manager", "admin"]
ROLE_LABELS = {
    "user": "User",
    "pentester": "Pentester",
    "manager": "Manager",
    "admin": "Admin",
}


def read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
    except Exception:
        return None
    return None


def load_manifest() -> Dict[str, Any]:
    manifest = read_json_file(DOCS_MANIFEST_PATH)
    if manifest is None:
        return {"sections": []}
    sections = manifest.get("sections")
    if not isinstance(sections, list):
        return {"sections": []}
    return {"sections": sections}


def find_page_in_manifest(manifest: Dict[str, Any], section_slug: str, page_slug: str):
    for section in manifest.get("sections", []):
        if section.get("slug") != section_slug:
            continue
        for page in section.get("pages", []):
            if page.get("slug") == page_slug:
                return page
    return None


def resolve_docs_content_path(section_slug: str, page_slug: str) -> Optional[str]:
    section = str(section_slug or "").strip()
    page = str(page_slug or "").strip()
    if not section or not page:
        return None

    candidate_path = os.path.abspath(os.path.join(DOCS_CONTENT_ROOT, section, f"{page}.json"))
    content_root = os.path.abspath(DOCS_CONTENT_ROOT)
    try:
        if os.path.commonpath([candidate_path, content_root]) != content_root:
            return None
    except ValueError:
        return None
    return candidate_path


__all__ = [
    "DOCS_CONTENT_ROOT",
    "ROLE_LABELS",
    "ROLE_ORDER",
    "find_page_in_manifest",
    "load_manifest",
    "read_json_file",
    "resolve_docs_content_path",
]
