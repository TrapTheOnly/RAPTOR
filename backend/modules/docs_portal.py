import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from modules.permissions import (
    PERMISSIONS,
    ROLE_DEFAULTS,
    ROLE_OPTIONAL,
    get_effective_permissions,
    get_user_permissions,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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


def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
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


def _load_manifest() -> Dict[str, Any]:
    manifest = _read_json_file(DOCS_MANIFEST_PATH)
    if manifest is None:
        return {"sections": []}
    sections = manifest.get("sections")
    if not isinstance(sections, list):
        return {"sections": []}
    return {"sections": sections}


def _resolve_user_context(
    username: Optional[str],
    role: Optional[str],
) -> Optional[Tuple[str, str, Set[str]]]:
    normalized_username = str(username or "").strip()
    normalized_role = str(role or "").strip().lower()
    if not normalized_username or not normalized_role:
        return None
    return normalized_username, normalized_role, set(
        get_user_permissions(normalized_username, normalized_role)
    )


def _is_access_allowed(
    access: Dict[str, Any],
    role: str,
    permissions: Set[str],
) -> bool:
    normalized_role = str(role or "").strip().lower()
    if not normalized_role:
        return False

    roles = access.get("roles", [])
    if roles:
        normalized_roles = {str(item).strip().lower() for item in roles}
        if normalized_role not in normalized_roles:
            return False

    require_all = access.get("require_all", [])
    if require_all:
        for permission in require_all:
            normalized_permission = str(permission).strip()
            if (
                normalized_permission not in PERMISSIONS
                or normalized_permission not in permissions
            ):
                return False

    require_any = access.get("require_any", [])
    if require_any:
        if not any(
            str(permission).strip() in PERMISSIONS
            and str(permission).strip() in permissions
            for permission in require_any
        ):
            return False

    return True


def _filter_manifest_for_user(
    manifest: Dict[str, Any],
    role: str,
    permissions: Set[str],
) -> Dict[str, Any]:
    sections_out: List[Dict[str, Any]] = []

    for section in manifest.get("sections", []):
        pages = section.get("pages") or []
        pages_out: List[Dict[str, Any]] = []

        for page in pages:
            access = page.get("access") or {}
            if _is_access_allowed(access, role, permissions):
                pages_out.append({
                    "slug": page.get("slug"),
                    "title": page.get("title"),
                    "audience": page.get("audience") or [],
                    "summary": page.get("summary") or "",
                    "coverage": page.get("coverage") or [],
                })

        if pages_out:
            sections_out.append({
                "slug": section.get("slug"),
                "title": section.get("title"),
                "description": section.get("description") or "",
                "pages": pages_out,
            })

    return {"sections": sections_out}


def get_docs_manifest_for_user(
    username: Optional[str],
    role: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    manifest = _load_manifest()
    context = _resolve_user_context(username, role)
    if not context:
        return {"sections": []}, 200
    _, normalized_role, permissions = context
    return _filter_manifest_for_user(manifest, normalized_role, permissions), 200


def _find_page_in_manifest(
    manifest: Dict[str, Any],
    section_slug: str,
    page_slug: str,
) -> Optional[Dict[str, Any]]:
    for section in manifest.get("sections", []):
        if section.get("slug") != section_slug:
            continue
        for page in section.get("pages", []):
            if page.get("slug") == page_slug:
                return page
    return None


def _build_access_rule_text(access: Dict[str, Any]) -> str:
    rules: List[str] = []
    roles = [str(item).strip().lower() for item in (access.get("roles") or []) if item]
    require_all = [str(item).strip() for item in (access.get("require_all") or []) if item]
    require_any = [str(item).strip() for item in (access.get("require_any") or []) if item]

    if roles:
        rules.append(f"roles in ({', '.join(sorted(roles))})")
    if require_all:
        rules.append(f"all of ({', '.join(sorted(require_all))})")
    if require_any:
        rules.append(f"any of ({', '.join(sorted(require_any))})")

    if not rules:
        return "Authenticated user"
    return " and ".join(rules)


def _flatten_manifest_pages(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    for section in manifest.get("sections", []):
        section_slug = section.get("slug")
        section_title = section.get("title")
        for page in section.get("pages", []):
            page_slug = page.get("slug")
            pages.append({
                "id": f"{section_slug}/{page_slug}",
                "section_slug": section_slug,
                "section_title": section_title,
                "page_slug": page_slug,
                "page_title": page.get("title"),
                "path": f"/docs/{section_slug}/{page_slug}",
                "access": page.get("access") or {},
            })
    pages.sort(key=lambda item: (str(item.get("section_title") or ""), str(item.get("page_title") or "")))
    return pages


def _build_role_scenarios(role: str) -> List[Dict[str, Any]]:
    normalized_role = str(role or "").strip().lower()
    optional_permissions = sorted(
        permission
        for permission in ROLE_OPTIONAL.get(normalized_role, set())
        if permission in PERMISSIONS
    )

    scenarios: List[Dict[str, Any]] = [
        {
            "key": f"{normalized_role}__base",
            "label": "Base role",
            "optional_permissions": [],
            "permissions": set(get_effective_permissions(normalized_role, [])),
        }
    ]

    for permission in optional_permissions:
        scenarios.append({
            "key": f"{normalized_role}__with_{permission}",
            "label": f"+ {permission}",
            "optional_permissions": [permission],
            "permissions": set(get_effective_permissions(normalized_role, [permission])),
        })

    if len(optional_permissions) > 1:
        scenarios.append({
            "key": f"{normalized_role}__with_all_optional",
            "label": "All optional grants",
            "optional_permissions": optional_permissions,
            "permissions": set(get_effective_permissions(normalized_role, optional_permissions)),
        })

    return scenarios


def _build_docs_access_matrix(manifest: Dict[str, Any]) -> Dict[str, Any]:
    pages = _flatten_manifest_pages(manifest)
    role_entries: List[Dict[str, Any]] = []

    manifest_roles = set(str(role).strip().lower() for role in ROLE_DEFAULTS.keys())
    ordered_roles = [role for role in ROLE_ORDER if role in manifest_roles]
    ordered_roles.extend(sorted(manifest_roles - set(ordered_roles)))

    for role in ordered_roles:
        scenarios = _build_role_scenarios(role)
        scenario_counts = {scenario["key"]: 0 for scenario in scenarios}
        rows: List[Dict[str, Any]] = []

        for page in pages:
            visibility: Dict[str, bool] = {}
            visible_in_any_scenario = False

            for scenario in scenarios:
                is_visible = _is_access_allowed(
                    page.get("access") or {},
                    role=role,
                    permissions=scenario.get("permissions") or set(),
                )
                visibility[scenario["key"]] = is_visible
                if is_visible:
                    scenario_counts[scenario["key"]] += 1
                    visible_in_any_scenario = True

            if visible_in_any_scenario:
                rows.append({
                    "section_title": page.get("section_title"),
                    "page_title": page.get("page_title"),
                    "path": page.get("path"),
                    "access_rule": _build_access_rule_text(page.get("access") or {}),
                    "visibility": visibility,
                })

        role_entries.append({
            "role": role,
            "role_label": ROLE_LABELS.get(role, role.title()),
            "scenarios": [
                {
                    "key": scenario["key"],
                    "label": scenario["label"],
                    "optional_permissions": scenario["optional_permissions"],
                    "visible_count": scenario_counts[scenario["key"]],
                }
                for scenario in scenarios
            ],
            "rows": rows,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_pages_in_manifest": len(pages),
        "roles": role_entries,
    }


def get_docs_page_for_user(
    section_slug: str,
    page_slug: str,
    username: Optional[str],
    role: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    context = _resolve_user_context(username, role)
    if not context:
        return {"error": "Unauthorized access"}, 403

    _, normalized_role, permissions = context
    manifest = _load_manifest()
    descriptor = _find_page_in_manifest(manifest, section_slug, page_slug)
    if not descriptor:
        return {"error": "Documentation page not found."}, 404

    access = descriptor.get("access") or {}
    if not _is_access_allowed(access, normalized_role, permissions):
        return {"error": "Unauthorized access"}, 403

    content_path = os.path.join(DOCS_CONTENT_ROOT, section_slug, f"{page_slug}.json")
    page_payload = _read_json_file(content_path)
    if page_payload is None:
        return {"error": "Documentation content not found."}, 404

    page_payload.pop("access", None)
    return {"page": page_payload}, 200


def get_docs_access_matrix_for_user(
    username: Optional[str],
    role: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    context = _resolve_user_context(username, role)
    if not context:
        return {"error": "Unauthorized access"}, 403

    _, normalized_role, _ = context
    if normalized_role != "admin":
        return {"error": "Unauthorized access"}, 403

    manifest = _load_manifest()
    matrix = _build_docs_access_matrix(manifest)
    return {"matrix": matrix}, 200
