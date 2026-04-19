PERMISSIONS = {
    "view_settings",
    "view_dashboard",
    "view_records",
    "view_security_dashboard",
    "create_manual_records",
    "modify_records",
    "view_record_details",
    "export_records",
    "manage_apps",
    "view_pentest_page",
    "modify_pentests",
    "export_pentests",
    "manage_ip_sources",
    "manage_vuln_categories",
    "manage_report_templates",
    "reassign_pentests_admin",
    "delete_records",
    "modify_others_pentests_admin",
}

ROLE_DEFAULTS = {
    "user": {
        "view_records",
        "modify_records",
        "view_record_details",
        "export_records",
    },
    "pentester": {
        "view_records",
        "view_security_dashboard",
        "view_record_details",
        "export_records",
        "view_pentest_page",
        "modify_pentests",
        "export_pentests",
    },
    "manager": {
        "view_settings",
        "view_dashboard",
        "view_records",
        "view_security_dashboard",
        "create_manual_records",
        "modify_records",
        "view_record_details",
        "export_records",
        "manage_ip_sources",
        "manage_vuln_categories",
        "manage_report_templates",
        "manage_apps",
        "view_pentest_page",
        "modify_pentests",
        "export_pentests",
        "reassign_pentests_admin",
        "delete_records",
        "modify_others_pentests_admin",
    },
    "admin": set(PERMISSIONS),
}

ROLE_OPTIONAL = {
    "user": {"view_dashboard", "view_security_dashboard", "manage_apps"},
    "pentester": {"view_dashboard", "modify_records", "manage_apps"},
    "manager": set(),
    "admin": set(),
}


def sanitize_extra_permissions(role, extra_permissions):
    allowed = ROLE_OPTIONAL.get(role, set())
    if not extra_permissions:
        return []
    return sorted({perm for perm in extra_permissions if perm in allowed})


def get_effective_permissions(role, extra_permissions=None):
    if role == "admin":
        return set(PERMISSIONS)
    base = set(ROLE_DEFAULTS.get(role, set()))
    extras = set(extra_permissions or [])
    extras = {perm for perm in extras if perm in ROLE_OPTIONAL.get(role, set())}
    return base | extras


__all__ = [
    "PERMISSIONS",
    "ROLE_DEFAULTS",
    "ROLE_OPTIONAL",
    "get_effective_permissions",
    "sanitize_extra_permissions",
]
