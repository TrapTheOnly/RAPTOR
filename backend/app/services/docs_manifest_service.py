from typing import Any, Dict, List, Optional, Set, Tuple

from app.domain.docs.manifest_schema import (
    find_page_in_manifest,
    load_manifest,
    read_json_file,
    resolve_docs_content_path,
)
from app.services.authorization_service import get_user_permissions
from app.services.docs_access_matrix_service import build_docs_access_matrix, is_access_allowed


def _resolve_user_context(username: Optional[str], role: Optional[str]) -> Optional[Tuple[str, str, Set[str]]]:
    normalized_username = str(username or "").strip()
    normalized_role = str(role or "").strip().lower()
    if not normalized_username or not normalized_role:
        return None
    return normalized_username, normalized_role, set(get_user_permissions(normalized_username, normalized_role))


def _filter_manifest_for_user(manifest: Dict[str, Any], role: str, permissions: Set[str]) -> Dict[str, Any]:
    sections_out: List[Dict[str, Any]] = []

    for section in manifest.get("sections", []):
        pages = section.get("pages") or []
        pages_out: List[Dict[str, Any]] = []

        for page in pages:
            access = page.get("access") or {}
            if is_access_allowed(access, role, permissions):
                pages_out.append(
                    {
                        "slug": page.get("slug"),
                        "title": page.get("title"),
                        "audience": page.get("audience") or [],
                        "summary": page.get("summary") or "",
                        "coverage": page.get("coverage") or [],
                    }
                )

        if pages_out:
            sections_out.append(
                {
                    "slug": section.get("slug"),
                    "title": section.get("title"),
                    "description": section.get("description") or "",
                    "pages": pages_out,
                }
            )

    return {"sections": sections_out}


def get_docs_manifest_for_user(username: Optional[str], role: Optional[str]):
    manifest = load_manifest()
    context = _resolve_user_context(username, role)
    if not context:
        return {"sections": []}, 200
    _, normalized_role, permissions = context
    return _filter_manifest_for_user(manifest, normalized_role, permissions), 200


def get_docs_page_for_user(section_slug: str, page_slug: str, username: Optional[str], role: Optional[str]):
    context = _resolve_user_context(username, role)
    if not context:
        return {"error": "Unauthorized access"}, 403

    _, normalized_role, permissions = context
    manifest = load_manifest()
    descriptor = find_page_in_manifest(manifest, section_slug, page_slug)
    if not descriptor:
        return {"error": "Documentation page not found."}, 404

    access = descriptor.get("access") or {}
    if not is_access_allowed(access, normalized_role, permissions):
        return {"error": "Unauthorized access"}, 403

    content_path = resolve_docs_content_path(section_slug, page_slug)
    if not content_path:
        return {"error": "Documentation content not found."}, 404
    page_payload = read_json_file(content_path)
    if page_payload is None:
        return {"error": "Documentation content not found."}, 404

    page_payload.pop("access", None)
    return {"page": page_payload}, 200


def get_docs_access_matrix_for_user(username: Optional[str], role: Optional[str]):
    context = _resolve_user_context(username, role)
    if not context:
        return {"error": "Unauthorized access"}, 403

    _, normalized_role, _ = context
    if normalized_role != "admin":
        return {"error": "Unauthorized access"}, 403

    manifest = load_manifest()
    matrix = build_docs_access_matrix(manifest)
    return {"matrix": matrix}, 200


__all__ = [
    "get_docs_access_matrix_for_user",
    "get_docs_manifest_for_user",
    "get_docs_page_for_user",
]
