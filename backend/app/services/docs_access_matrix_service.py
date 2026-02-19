from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from app.domain.auth.permissions import PERMISSIONS, ROLE_DEFAULTS, ROLE_OPTIONAL, get_effective_permissions
from app.domain.docs.manifest_schema import ROLE_LABELS, ROLE_ORDER


def is_access_allowed(access: Dict[str, Any], role: str, permissions: Set[str]) -> bool:
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
            if normalized_permission not in PERMISSIONS or normalized_permission not in permissions:
                return False

    require_any = access.get("require_any", [])
    if require_any:
        if not any(
            str(permission).strip() in PERMISSIONS and str(permission).strip() in permissions
            for permission in require_any
        ):
            return False

    return True


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
            pages.append(
                {
                    "id": f"{section_slug}/{page_slug}",
                    "section_slug": section_slug,
                    "section_title": section_title,
                    "page_slug": page_slug,
                    "page_title": page.get("title"),
                    "path": f"/docs/{section_slug}/{page_slug}",
                    "access": page.get("access") or {},
                }
            )
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
        scenarios.append(
            {
                "key": f"{normalized_role}__with_{permission}",
                "label": f"+ {permission}",
                "optional_permissions": [permission],
                "permissions": set(get_effective_permissions(normalized_role, [permission])),
            }
        )

    if len(optional_permissions) > 1:
        scenarios.append(
            {
                "key": f"{normalized_role}__with_all_optional",
                "label": "All optional grants",
                "optional_permissions": optional_permissions,
                "permissions": set(get_effective_permissions(normalized_role, optional_permissions)),
            }
        )

    return scenarios


def build_docs_access_matrix(manifest: Dict[str, Any]) -> Dict[str, Any]:
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
                is_visible = is_access_allowed(
                    page.get("access") or {},
                    role=role,
                    permissions=scenario.get("permissions") or set(),
                )
                visibility[scenario["key"]] = is_visible
                if is_visible:
                    scenario_counts[scenario["key"]] += 1
                    visible_in_any_scenario = True

            if visible_in_any_scenario:
                rows.append(
                    {
                        "section_title": page.get("section_title"),
                        "page_title": page.get("page_title"),
                        "path": page.get("path"),
                        "access_rule": _build_access_rule_text(page.get("access") or {}),
                        "visibility": visibility,
                    }
                )

        role_entries.append(
            {
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
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_pages_in_manifest": len(pages),
        "roles": role_entries,
    }


__all__ = ["build_docs_access_matrix", "is_access_allowed"]
