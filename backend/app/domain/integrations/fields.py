"""Raptor → Jira / DefectDojo field catalog, mapping heuristics, and payload build."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

RAPTOR_FIELDS: List[Dict[str, str]] = [
    {"id": "title", "label": "Title", "type": "string"},
    {"id": "description", "label": "Description", "type": "text"},
    {"id": "impact", "label": "Impact", "type": "text"},
    {"id": "evidence", "label": "Evidence", "type": "text"},
    {"id": "remediation", "label": "Remediation", "type": "text"},
    {"id": "severity", "label": "Severity", "type": "option"},
    {"id": "cvss_score", "label": "CVSS score", "type": "number"},
    {"id": "category", "label": "Category", "type": "string"},
    {"id": "status", "label": "Status", "type": "string"},
    {"id": "auth_context", "label": "Auth context", "type": "string"},
    {"id": "hosts", "label": "Affected hosts", "type": "text"},
    {"id": "environments", "label": "Environments", "type": "string"},
    {"id": "application", "label": "Application", "type": "string"},
    {"id": "wave", "label": "Wave", "type": "string"},
    {"id": "reporter", "label": "Reporter", "type": "string"},
    {"id": "collaborators", "label": "Collaborators", "type": "string"},
    {"id": "found_here", "label": "Found-here host", "type": "string"},
]

FILL_MODES: List[Dict[str, str]] = [
    {"id": "mapped", "label": "Fill from RAPTOR"},
    {"id": "ask", "label": "Ask when sending"},
    {"id": "static", "label": "Fixed value"},
    {"id": "skip", "label": "Ignore"},
]

KINDS: List[Dict[str, str]] = [
    {"id": "jira", "label": "Jira"},
    {"id": "defectdojo", "label": "DefectDojo"},
]

JIRA_SKIP_KEYS = {
    "project",
    "issuetype",
    "attachment",
    "issuelinks",
    "comment",
    "worklog",
    "timetracking",
    "parent",
    "subtasks",
    "thumbnail",
    "status",
    "resolution",
    "votes",
    "watches",
    "workratio",
    "lastviewed",
    "creator",
    "created",
    "updated",
    "aggregatetimeoriginalestimate",
    "aggregatetimeestimate",
    "aggregatetimespent",
    "timeoriginalestimate",
    "timeestimate",
    "timespent",
}

_SEVERITY_ALIASES = {
    "critical": ("critical", "highest", "blocker"),
    "high": ("high", "major"),
    "medium": ("medium", "moderate", "normal"),
    "low": ("low", "minor"),
    "info": ("info", "informational", "lowest", "trivial"),
}

_JIRA_AUTO_MAP = {
    "summary": "title",
    "description": "description,impact,evidence,remediation",
    "priority": "severity",
    "labels": "category",
}

_DOJO_AUTO_MAP = {
    "title": "title",
    "description": "description",
    "severity": "severity",
    "cvssv3_score": "cvss_score",
    "mitigation": "remediation",
    "impact": "impact",
    "steps_to_reproduce": "evidence",
}

NARRATIVE_FIELD_IDS: Tuple[str, ...] = ("description", "impact", "evidence", "remediation")
_NARRATIVE_LABELS = {item["id"]: item["label"] for item in RAPTOR_FIELDS if item["id"] in NARRATIVE_FIELD_IDS}


def catalog() -> Dict[str, Any]:
    return {
        "raptor_fields": list(RAPTOR_FIELDS),
        "fill_modes": list(FILL_MODES),
        "kinds": list(KINDS),
    }


def severity_from_score(score: Any) -> str:
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0.0
    if value >= 9.0:
        return "critical"
    if value >= 7.0:
        return "high"
    if value >= 4.0:
        return "medium"
    if value > 0:
        return "low"
    return "info"


def severity_label(key: str) -> str:
    return {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "info": "Info",
        "informational": "Info",
        "s0": "Critical",
        "s1": "High",
        "s2": "Medium",
        "s3": "Low",
        "s4": "Info",
    }.get(str(key or "").lower(), "Info")


def dojo_numerical_severity(label: str) -> str:
    return {
        "critical": "S0",
        "high": "S1",
        "medium": "S2",
        "low": "S3",
        "info": "S4",
        "informational": "S4",
        "s0": "S0",
        "s1": "S1",
        "s2": "S2",
        "s3": "S3",
        "s4": "S4",
    }.get(str(label or "").strip().lower(), "S4")


def slugify_label(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip()).strip("-").lower()
    return cleaned[:255]


_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_OPEN = re.compile(r"^```([\w+-]*)\s*$")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_PENTEST_IMAGE = re.compile(
    r"(?:https?://[^/\s]+)?/pentest/images/([a-f0-9]{32}\.(?:png|jpg|jpeg|gif|webp))",
    re.IGNORECASE,
)

# Jira Server/DC code macro languages (Code Macro / Syntax Highlighter).
_JIRA_CODE_LANGUAGES = {
    "actionscript",
    "ada",
    "applescript",
    "bash",
    "c",
    "c#",
    "c++",
    "cpp",
    "css",
    "erlang",
    "go",
    "groovy",
    "haskell",
    "html",
    "java",
    "javascript",
    "js",
    "json",
    "lua",
    "none",
    "nyan",
    "objc",
    "perl",
    "php",
    "python",
    "r",
    "rainbow",
    "ruby",
    "scala",
    "sh",
    "sql",
    "swift",
    "visualbasic",
    "xml",
    "yaml",
}
_JIRA_CODE_ALIASES = {
    "shell": "bash",
    "zsh": "bash",
    "fish": "bash",
    "console": "bash",
    "terminal": "bash",
    "py": "python",
    "rb": "ruby",
    "ts": "javascript",
    "typescript": "javascript",
    "jsx": "javascript",
    "tsx": "javascript",
    "yml": "yaml",
    "csharp": "c#",
    "objective-c": "objc",
    "vb": "visualbasic",
    "http": "",
    "https": "",
    "httprequest": "",
    "text": "",
    "plaintext": "",
    "txt": "",
    "output": "",
    "md": "",
    "markdown": "",
    "diff": "",
    "dockerfile": "",
    "docker": "",
    "ini": "",
    "toml": "",
    "rust": "",
    "rs": "",
    "ps1": "",
    "powershell": "",
}


def _jira_code_language(lang: str) -> str:
    key = str(lang or "").strip().lower()
    if not key:
        return ""
    mapped = _JIRA_CODE_ALIASES[key] if key in _JIRA_CODE_ALIASES else key
    if mapped in _JIRA_CODE_LANGUAGES:
        return mapped
    return ""


def _wiki_code_open(lang: str) -> str:
    mapped = _jira_code_language(lang)
    return f"{{code:{mapped}}}" if mapped else "{code}"


def _wiki_inline_code(text: str) -> str:
    def replace(match: re.Match) -> str:
        body = match.group(1)
        if not body.strip() or "{{" in body or "}}" in body:
            return match.group(0)
        return "{{" + body + "}}"

    return _INLINE_CODE.sub(replace, text)


def pentest_image_filenames(text: str) -> List[str]:
    seen = []
    for match in _PENTEST_IMAGE.findall(str(text or "")):
        name = str(match).lower()
        if name not in seen:
            seen.append(name)
    return seen


def replace_pentest_images_with_attach_note(text: str) -> str:
    def repl(match: re.Match) -> str:
        alt = (match.group(1) or "").strip()
        url = match.group(2) or ""
        names = pentest_image_filenames(url)
        if not names:
            return match.group(0)
        note = f"Screenshot attached as `{names[0]}`"
        if alt:
            note += f" ({alt})"
        return note + "."

    return _MD_IMAGE.sub(repl, str(text or ""))


def narrative_image_filenames(values: Dict[str, Any]) -> List[str]:
    blob = "\n".join(str(values.get(item) or "") for item in NARRATIVE_FIELD_IDS)
    return pentest_image_filenames(blob)


def _wiki_image(alt: str, url: str) -> str:
    match = _PENTEST_IMAGE.search(url or "")
    name = match.group(1).lower() if match else str(url or "").strip()
    if not name:
        return alt or ""
    label = re.sub(r'[|"!]', " ", alt or "").strip()
    if label:
        return f'!{name}|thumbnail, alt="{label}"!'
    return f"!{name}|thumbnail!"


def _adf_text_paragraph(text: str) -> Dict[str, Any]:
    if not text:
        return {"type": "paragraph", "content": []}
    return {"type": "paragraph", "content": [{"type": "text", "text": text[:32767]}]}


def _adf_inline_content(text: str) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = []
    cursor = 0
    for match in _MD_IMAGE.finditer(text):
        if match.start() > cursor:
            chunk = text[cursor : match.start()]
            if chunk:
                content.append({"type": "text", "text": chunk[:32767]})
        alt = (match.group(1) or "").strip() or "screenshot"
        content.append({"type": "text", "text": f"[{alt}]"})
        cursor = match.end()
    if cursor < len(text):
        chunk = text[cursor:]
        if chunk:
            content.append({"type": "text", "text": chunk[:32767]})
    return content or [{"type": "text", "text": text[:32767]}]


def to_adf(text: str) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = []
    in_fence = False
    fence_lang = ""
    fence_lines: List[str] = []
    for block in str(text or "").split("\n"):
        fence = _FENCE_OPEN.match(block.strip())
        if fence:
            if not in_fence:
                in_fence = True
                fence_lang = _jira_code_language(fence.group(1) or "")
                fence_lines = []
            else:
                in_fence = False
                node: Dict[str, Any] = {
                    "type": "codeBlock",
                    "content": [{"type": "text", "text": "\n".join(fence_lines) or " "}],
                }
                if fence_lang:
                    node["attrs"] = {"language": fence_lang}
                content.append(node)
            continue
        if in_fence:
            fence_lines.append(block)
            continue
        if block == "":
            content.append({"type": "paragraph", "content": []})
            continue
        heading = _ATX_HEADING.match(block)
        if heading:
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": min(len(heading.group(1)), 6)},
                    "content": [{"type": "text", "text": heading.group(2)[:32767]}],
                }
            )
            continue
        if _MD_IMAGE.fullmatch(block.strip()):
            match = _MD_IMAGE.fullmatch(block.strip())
            alt = (match.group(1) or "").strip() or "screenshot"
            content.append(_adf_text_paragraph(f"[{alt}]"))
            continue
        content.append({"type": "paragraph", "content": _adf_inline_content(block)})
    if in_fence:
        node = {
            "type": "codeBlock",
            "content": [{"type": "text", "text": "\n".join(fence_lines) or " "}],
        }
        if fence_lang:
            node["attrs"] = {"language": fence_lang}
        content.append(node)
    if not content:
        content = [{"type": "paragraph", "content": []}]
    return {"type": "doc", "version": 1, "content": content}


def to_jira_wiki(text: str) -> str:
    """Translate RAPTOR markdown into Jira Server/DC wiki markup.

    ``#`` is a numbered list in wiki, so ATX headings become ``h2.``. Fences
    become ``{code}`` blocks. RAPTOR screenshots become attached-image
    markup (``!hash.png|thumbnail!``) so Jira can render them inline after
    the files are uploaded onto the issue.
    """
    lines: List[str] = []
    in_fence = False
    fence_lang = ""
    for line in str(text or "").splitlines():
        fence = _FENCE_OPEN.match(line.strip())
        if fence:
            if not in_fence:
                in_fence = True
                fence_lang = _jira_code_language(fence.group(1) or "")
                lines.append(_wiki_code_open(fence.group(1) or ""))
            else:
                in_fence = False
                fence_lang = ""
                lines.append("{code}")
            continue
        if in_fence:
            lines.append(line)
            continue
        heading = _ATX_HEADING.match(line)
        if heading:
            lines.append(f"h{min(len(heading.group(1)), 6)}. {_wiki_inline_code(heading.group(2))}")
            continue
        lines.append(
            _wiki_inline_code(_MD_IMAGE.sub(lambda match: _wiki_image(match.group(1), match.group(2)), line))
        )
    if in_fence:
        lines.append("{code}")
    return "\n".join(lines)


def parse_raptor_fields(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        parts = [str(item).strip() for item in value]
    else:
        parts = [part.strip() for part in str(value or "").split(",")]
    known = {item["id"] for item in RAPTOR_FIELDS}
    return [item for item in parts if item and item in known]


def join_raptor_fields(ids: Iterable[str]) -> str:
    wanted = {str(item).strip() for item in ids if str(item).strip()}
    ordered = [item for item in NARRATIVE_FIELD_IDS if item in wanted]
    extra = [item for item in parse_raptor_fields(",".join(wanted)) if item not in NARRATIVE_FIELD_IDS]
    return ",".join(ordered + extra)


def is_narrative_combine_field(field_id: str, field_name: str = "", field_type: str = "") -> bool:
    ident = str(field_id or "").strip().lower()
    name = str(field_name or "").strip().lower()
    kind = str(field_type or "").strip().lower()
    if ident == "summary":
        return False
    if ident == "description":
        return True
    return kind in {"text", "doc"} and "description" in name


def compose_narrative(field_ids: Sequence[str], values: Dict[str, Any]) -> str:
    parsed = parse_raptor_fields(list(field_ids) if not isinstance(field_ids, str) else field_ids)
    ids = [item for item in NARRATIVE_FIELD_IDS if item in parsed]
    ids.extend(item for item in parsed if item not in NARRATIVE_FIELD_IDS)
    if not ids:
        return ""
    parts: List[str] = []
    use_headings = len(ids) > 1
    for field_id in ids:
        if field_id == "severity":
            body = str(values.get("severity_label") or "").strip()
        else:
            body = str(values.get(field_id) or "").strip()
        if not body:
            continue
        if use_headings:
            label = _NARRATIVE_LABELS.get(field_id) or next(
                (item["label"] for item in RAPTOR_FIELDS if item["id"] == field_id),
                field_id.replace("_", " ").title(),
            )
            parts.append(f"## {label}\n\n{body}")
        else:
            parts.append(body)
    return "\n\n".join(parts)


def classify_jira_schema(schema: Optional[Dict[str, Any]], field_id: str) -> str:
    schema = schema or {}
    system = str(schema.get("system") or "").lower()
    type_name = str(schema.get("type") or "").lower()
    items = str(schema.get("items") or "").lower()
    custom = str(schema.get("custom") or "").lower()
    key = str(field_id or "").lower()

    if key in JIRA_SKIP_KEYS or system in JIRA_SKIP_KEYS:
        return "skip"
    if type_name in {"priority"} or system == "priority" or key == "priority":
        return "priority"
    if type_name in {"user", "watcher"} or "userpicker" in custom:
        return "user"
    if type_name in {"number"}:
        return "number"
    if type_name in {"date"}:
        return "date"
    if type_name in {"datetime"}:
        return "datetime"
    if type_name in {"option"} or "select" in custom and "multi" not in custom:
        return "option"
    if type_name == "array":
        if items in {"option", "component", "version"} or "multiselect" in custom or "checkbox" in custom:
            return "multioption"
        if items in {"string"} or "labels" in custom or key == "labels":
            return "labels"
        if items == "user":
            return "user"
        return "labels"
    if type_name in {"string"} and (system == "description" or key == "description" or "textarea" in custom):
        return "text"
    if type_name in {"any", "doc"} or system == "description" or "atlassian:adf" in custom:
        return "doc"
    if type_name in {"string"}:
        return "string"
    return "string"


def normalize_allowed_values(raw: Any) -> List[Dict[str, str]]:
    values: List[Dict[str, str]] = []
    if not isinstance(raw, list):
        return values
    for item in raw:
        if not isinstance(item, dict):
            text = str(item)
            values.append({"id": text, "label": text, "value": text})
            continue
        ident = str(item.get("id") or item.get("accountId") or item.get("key") or "")
        label = str(item.get("name") or item.get("value") or item.get("label") or ident)
        value = str(item.get("value") or item.get("name") or label)
        if not ident:
            ident = value
        values.append({"id": ident, "label": label, "value": value})
    return values


def parse_jira_fields(createmeta_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    for field_id, spec in (createmeta_fields or {}).items():
        if not isinstance(spec, dict):
            continue
        field_type = classify_jira_schema(spec.get("schema") or {}, field_id)
        if field_type == "skip":
            continue
        allowed = normalize_allowed_values(spec.get("allowedValues") or [])
        parsed.append(
            {
                "id": str(field_id),
                "name": str(spec.get("name") or field_id),
                "type": field_type,
                "required": bool(spec.get("required")),
                "allowed_values": allowed,
                "custom": str(field_id).startswith("customfield_"),
                "has_default": spec.get("hasDefaultValue") is True,
            }
        )
    parsed.sort(key=lambda item: (not item["required"], item["name"].lower()))
    return parsed


def defectdojo_fields() -> List[Dict[str, Any]]:
    return [
        {
            "id": "title",
            "name": "Title",
            "type": "string",
            "required": True,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "description",
            "name": "Description",
            "type": "text",
            "required": True,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "severity",
            "name": "Severity",
            "type": "option",
            "required": True,
            "allowed_values": [
                {"id": key, "label": severity_label(key), "value": severity_label(key)}
                for key in ("critical", "high", "medium", "low", "info")
            ],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "cvssv3_score",
            "name": "CVSS score",
            "type": "number",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "mitigation",
            "name": "Mitigation",
            "type": "text",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "impact",
            "name": "Impact",
            "type": "text",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "steps_to_reproduce",
            "name": "Steps to reproduce",
            "type": "text",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "tags",
            "name": "Tags",
            "type": "labels",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "references",
            "name": "References",
            "type": "text",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "component_name",
            "name": "Component name",
            "type": "string",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "component_version",
            "name": "Component version",
            "type": "string",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "unique_id_from_tool",
            "name": "Unique ID from tool",
            "type": "string",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
        {
            "id": "planned_remediation_date",
            "name": "Planned remediation date",
            "type": "date",
            "required": False,
            "allowed_values": [],
            "custom": False,
            "has_default": False,
        },
    ]


def suggest_raptor_field(kind: str, field_id: str, field_name: str) -> str:
    key = str(field_id or "").lower()
    name = str(field_name or "").lower()
    table = _JIRA_AUTO_MAP if kind == "jira" else _DOJO_AUTO_MAP
    if kind == "jira" and is_narrative_combine_field(field_id, field_name):
        return table.get("description") or ",".join(NARRATIVE_FIELD_IDS)
    if key in table:
        return table[key]
    for candidate, raptor in table.items():
        if candidate in name:
            return raptor
    return ""


def default_fill_mode(kind: str, field: Dict[str, Any]) -> str:
    mapped = suggest_raptor_field(kind, field.get("id") or "", field.get("name") or "")
    if mapped:
        return "mapped"
    if field.get("required") and not field.get("has_default"):
        return "ask"
    return "skip"


def seed_mappings(kind: str, fields: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mappings = []
    for index, field in enumerate(fields):
        raptor = suggest_raptor_field(kind, field.get("id") or "", field.get("name") or "")
        mode = default_fill_mode(kind, field)
        mappings.append(
            {
                "raptor_field": raptor if mode == "mapped" else "",
                "external_field_id": field["id"],
                "external_field_name": field.get("name") or field["id"],
                "external_field_type": field.get("type") or "string",
                "fill_mode": mode,
                "static_value": "",
                "required": bool(field.get("required")),
                "allowed_values": list(field.get("allowed_values") or []),
                "sort_order": index,
            }
        )
    return mappings


def merge_mappings(
    live_fields: Sequence[Dict[str, Any]],
    saved: Sequence[Dict[str, Any]],
    kind: str,
) -> List[Dict[str, Any]]:
    by_id = {str(item.get("external_field_id")): item for item in saved or [] if item.get("external_field_id")}
    merged = []
    for index, field in enumerate(live_fields):
        existing = by_id.get(str(field["id"]))
        if existing:
            merged.append(
                {
                    **existing,
                    "external_field_name": field.get("name") or existing.get("external_field_name"),
                    "external_field_type": field.get("type") or existing.get("external_field_type"),
                    "required": bool(field.get("required")),
                    "allowed_values": list(field.get("allowed_values") or existing.get("allowed_values") or []),
                    "sort_order": index,
                }
            )
            continue
        seeded = seed_mappings(kind, [field])[0]
        seeded["sort_order"] = index
        merged.append(seeded)
    return merged


def raptor_values(finding_context: Dict[str, Any]) -> Dict[str, Any]:
    finding = finding_context.get("finding") or {}
    occurrences = finding.get("occurrences") or []
    hosts = []
    envs = []
    for item in occurrences:
        name = item.get("dns_name") or item.get("name")
        if name:
            hosts.append(str(name))
        slug = item.get("environment_slug")
        if slug:
            envs.append(str(slug))
    found_here = finding_context.get("found_here") or {}
    if found_here.get("name") and found_here["name"] not in hosts:
        hosts.insert(0, str(found_here["name"]))
    environment = finding_context.get("environment") or {}
    if environment.get("slug"):
        envs.insert(0, str(environment.get("slug")))
    wave = finding_context.get("wave") or {}
    application = finding_context.get("application") or {}
    score = finding.get("baseScore")
    if score is None:
        score = finding.get("base_score")
    severity = severity_from_score(score)
    collaborators = finding.get("collaborators") or []
    if isinstance(collaborators, str):
        collaborators = [collaborators]
    return {
        "title": str(finding.get("title") or finding.get("categoryName") or "Untitled finding")[:255],
        "description": str(finding.get("description") or ""),
        "impact": str(finding.get("impact") or ""),
        "evidence": str(finding.get("evidence") or ""),
        "remediation": str(finding.get("remediation") or ""),
        "severity": severity,
        "severity_label": severity_label(severity),
        "cvss_score": score if score not in (None, "") else "",
        "category": str(finding.get("categoryName") or finding.get("category_name") or ""),
        "status": str(finding.get("status") or ""),
        "auth_context": str(finding.get("auth_context") or ""),
        "hosts": ", ".join(dict.fromkeys(hosts)),
        "environments": ", ".join(dict.fromkeys(envs)),
        "application": str(application.get("name") or ""),
        "wave": str(wave.get("name") or ""),
        "reporter": str(finding.get("created_by") or ""),
        "collaborators": ", ".join(str(item) for item in collaborators if item),
        "found_here": str(found_here.get("name") or ""),
    }


def match_option(needle: str, options: Sequence[Dict[str, str]]) -> Optional[Dict[str, str]]:
    text = str(needle or "").strip().lower()
    if not text or not options:
        return None
    aliases = set(_SEVERITY_ALIASES.get(text, ()))
    aliases.add(text)
    for option in options:
        label = str(option.get("label") or "").strip().lower()
        value = str(option.get("value") or "").strip().lower()
        ident = str(option.get("id") or "").strip().lower()
        if label in aliases or value in aliases or ident == text:
            return dict(option)
    for option in options:
        label = str(option.get("label") or "").strip().lower()
        if any(alias in label or label in alias for alias in aliases if alias):
            return dict(option)
    return None


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def mapped_preview(mapping: Dict[str, Any], values: Dict[str, Any]) -> Any:
    mode = str(mapping.get("fill_mode") or "skip")
    if mode == "static":
        return mapping.get("static_value") or ""
    if mode != "mapped":
        return ""
    field_ids = parse_raptor_fields(mapping.get("raptor_field") or "")
    if not field_ids:
        return ""
    if len(field_ids) == 1 and field_ids[0] == "severity":
        return values.get("severity_label") or ""
    if len(field_ids) == 1:
        return values.get(field_ids[0]) or ""
    return compose_narrative(field_ids, values)


def _jira_option_payload(option: Dict[str, str], field_type: str) -> Any:
    ident = option.get("id") or ""
    name = option.get("label") or option.get("value") or ident
    if field_type == "priority":
        return {"id": ident} if ident else {"name": name}
    if ident and ident != name:
        return {"id": ident}
    return {"value": option.get("value") or name}


def build_jira_field_value(
    mapping: Dict[str, Any],
    values: Dict[str, Any],
    extras: Dict[str, Any],
    *,
    adf: bool,
) -> Tuple[Optional[Any], Optional[str]]:
    field_id = str(mapping.get("external_field_id") or "")
    field_type = str(mapping.get("external_field_type") or "string")
    mode = str(mapping.get("fill_mode") or "skip")
    if mode == "skip":
        return None, None
    if mode == "ask":
        raw = extras.get(field_id)
        if raw in (None, "", []):
            if mapping.get("required"):
                return None, f"{mapping.get('external_field_name') or field_id} is required."
            return None, None
    elif mode == "static":
        raw = mapping.get("static_value")
    else:
        raw = mapped_preview(mapping, values)

    if raw in (None, "", []) and mapping.get("required"):
        return None, f"{mapping.get('external_field_name') or field_id} is required."
    if raw in (None, "", []):
        return None, None

    options = mapping.get("allowed_values") or []
    if field_type in {"option", "priority"}:
        if isinstance(raw, dict):
            option = raw
        else:
            option = match_option(str(raw), options) or {"id": str(raw), "label": str(raw), "value": str(raw)}
        return _jira_option_payload(option, field_type), None
    if field_type == "multioption":
        items = raw if isinstance(raw, list) else [part.strip() for part in str(raw).split(",") if part.strip()]
        payload = []
        for item in items:
            option = item if isinstance(item, dict) else match_option(str(item), options) or {
                "id": str(item),
                "label": str(item),
                "value": str(item),
            }
            payload.append(_jira_option_payload(option, "option"))
        return payload, None
    if field_type == "labels":
        if isinstance(raw, list):
            labels = [slugify_label(str(item)) for item in raw if str(item).strip()]
        else:
            labels = [slugify_label(part) for part in str(raw).replace(",", " ").split() if part.strip()]
        return [item for item in labels if item], None
    if field_type == "number":
        try:
            return float(raw), None
        except (TypeError, ValueError):
            return None, f"{mapping.get('external_field_name') or field_id} must be a number."
    if field_type == "user":
        text = _scalar(raw)
        if len(text) > 20 and "-" in text:
            return {"accountId": text}, None
        return {"name": text}, None
    if field_type in {"doc", "text"} and field_id == "description" and adf:
        return to_adf(_scalar(raw)), None
    if field_type == "doc" and adf:
        return to_adf(_scalar(raw)), None
    if field_type in {"doc", "text"}:
        return to_jira_wiki(_scalar(raw)), None
    if field_id == "summary":
        return _scalar(raw)[:255], None
    return _scalar(raw), None


def build_jira_issue_fields(
    mappings: Sequence[Dict[str, Any]],
    values: Dict[str, Any],
    extras: Dict[str, Any],
    project_key: str,
    issue_type_id: str,
    *,
    adf: bool,
) -> Tuple[Dict[str, Any], List[str]]:
    fields: Dict[str, Any] = {
        "project": {"key": project_key},
        "issuetype": {"id": str(issue_type_id)},
    }
    errors: List[str] = []
    for mapping in mappings:
        if str(mapping.get("external_field_id") or "") in {"project", "issuetype"}:
            continue
        value, error = build_jira_field_value(mapping, values, extras, adf=adf)
        if error:
            errors.append(error)
            continue
        if value is None:
            continue
        fields[str(mapping["external_field_id"])] = value
    return fields, errors


def build_defectdojo_finding(
    mappings: Sequence[Dict[str, Any]],
    values: Dict[str, Any],
    extras: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    payload: Dict[str, Any] = {}
    errors: List[str] = []
    for mapping in mappings:
        field_id = str(mapping.get("external_field_id") or "")
        mode = str(mapping.get("fill_mode") or "skip")
        if mode == "skip" or not field_id:
            continue
        if mode == "ask":
            raw = extras.get(field_id)
        elif mode == "static":
            raw = mapping.get("static_value")
        else:
            raw = mapped_preview(mapping, values)
        if raw in (None, "", []) and mapping.get("required"):
            errors.append(f"{mapping.get('external_field_name') or field_id} is required.")
            continue
        if raw in (None, "", []):
            continue
        if field_id == "severity":
            option = match_option(str(raw), mapping.get("allowed_values") or []) or {"value": severity_label(str(raw))}
            payload["severity"] = option.get("value") or option.get("label") or "Info"
            payload["numerical_severity"] = dojo_numerical_severity(payload["severity"])
            continue
        if field_id == "cvssv3_score":
            try:
                payload["cvssv3_score"] = float(raw)
            except (TypeError, ValueError):
                errors.append("CVSS score must be a number.")
            continue
        if field_id == "tags":
            if isinstance(raw, list):
                payload["tags"] = [str(item) for item in raw if str(item).strip()]
            else:
                payload["tags"] = [part.strip() for part in str(raw).replace(",", " ").split() if part.strip()]
            continue
        payload[field_id] = replace_pentest_images_with_attach_note(raw) if isinstance(raw, str) else raw
    return payload, errors


def ask_fields(mappings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in mappings if str(item.get("fill_mode") or "") == "ask"]


def mapped_fields(mappings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in mappings if str(item.get("fill_mode") or "") == "mapped"]
