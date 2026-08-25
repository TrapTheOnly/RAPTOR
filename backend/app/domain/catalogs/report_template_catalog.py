import copy
import hashlib
import json


DEFAULT_REPORT_TEMPLATE = {
    "key": "manager_executive",
    "name": "Manager Executive Report",
    "description": "Executive report with occurrence metrics, named charts, and detailed findings.",
    "version": 1,
    "branding": {
        "company_name": "Security Operations",
        "primary_color": "#067A8A",
        "accent_color": "#1E293B",
        "logo_url": ""
    },
    "placeholders": {
        "report_title": "Penetration Testing Report",
        "report_subtitle": "Assessment and remediation overview",
        "prepared_by": "{{pentest.tested_by}}",
        "prepared_for": "{{application.name}}"
    },
    "blocks": [
        {
            "type": "cover",
            "title": "{{report_title}}",
            "subtitle": "{{report_subtitle}}",
            "show_logo": True
        },
        {
            "type": "engagement_overview",
            "title": "Engagement Overview"
        },
        {
            "type": "key_metrics",
            "title": "Risk Snapshot"
        },
        {
            "type": "table_of_contents",
            "title": "Table of Contents"
        },
        {
            "type": "chart",
            "title": "Vulnerability Severity",
            "chart": "vulnerability_severity"
        },
        {
            "type": "chart",
            "title": "Occurrence Status",
            "chart": "occurrence_status"
        },
        {
            "type": "vulnerabilities",
            "title": "Detailed Findings",
            "include_descriptions": True
        },
        {
            "type": "text",
            "title": "Management Summary",
            "content": (
                "Findings: {{metrics.vulnerability_count}}. "
                "Critical/High: {{metrics.critical_high_count}}. "
                "Open-like occurrences: {{metrics.open_like_count}}."
            )
        }
    ]
}


CANONICAL_REPORT_TEMPLATES = (DEFAULT_REPORT_TEMPLATE,)


def get_canonical_report_templates():
    """Returns deep-copy-safe canonical report templates."""
    return copy.deepcopy(list(CANONICAL_REPORT_TEMPLATES))


def get_canonical_report_template_by_key(template_key):
    for template in CANONICAL_REPORT_TEMPLATES:
        if template.get("key") == template_key:
            return copy.deepcopy(template)
    return None


def build_report_template_revision(template):
    payload = json.dumps(template, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
