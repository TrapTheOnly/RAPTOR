import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CHECKLISTS_DIR = BASE_DIR / "checklists"
MANIFEST_PATH = CHECKLISTS_DIR / "manifest.json"


class ChecklistCatalogError(Exception):
    """Raised when checklist catalog files are invalid."""


REQUIRED_TEMPLATE_FIELDS = {
    "key",
    "name",
    "service",
    "source",
    "auto_ports",
    "sections",
}
REQUIRED_ITEM_FIELDS = {"id", "testName", "description", "tools"}


def _ensure(condition, message):
    if not condition:
        raise ChecklistCatalogError(message)


def _is_int_port(value):
    return isinstance(value, int) and 1 <= value <= 65535


def _validate_item(template_key, section_name, item, seen_ids):
    _ensure(isinstance(item, dict), f"Checklist '{template_key}' section '{section_name}' has non-object item.")
    missing = REQUIRED_ITEM_FIELDS - set(item.keys())
    _ensure(not missing, f"Checklist '{template_key}' item missing fields: {sorted(missing)}")

    item_id = str(item.get("id", "")).strip()
    test_name = str(item.get("testName", "")).strip()
    _ensure(item_id, f"Checklist '{template_key}' has item with empty id.")
    _ensure(test_name, f"Checklist '{template_key}' item '{item_id}' has empty testName.")
    _ensure(item_id not in seen_ids, f"Checklist '{template_key}' has duplicate item id '{item_id}'.")
    seen_ids.add(item_id)



def _validate_template(template):
    _ensure(isinstance(template, dict), "Checklist template file must contain a JSON object.")
    missing = REQUIRED_TEMPLATE_FIELDS - set(template.keys())
    _ensure(not missing, f"Checklist template '{template.get('key', 'unknown')}' missing fields: {sorted(missing)}")

    key = str(template.get("key", "")).strip()
    _ensure(key, "Checklist key must be non-empty.")

    auto_ports = template.get("auto_ports")
    _ensure(isinstance(auto_ports, list), f"Checklist '{key}' auto_ports must be a list.")
    for port in auto_ports:
        _ensure(_is_int_port(port), f"Checklist '{key}' has invalid auto port '{port}'.")

    sections = template.get("sections")
    _ensure(isinstance(sections, list) and sections, f"Checklist '{key}' sections must be a non-empty list.")

    seen_item_ids = set()
    for section in sections:
        _ensure(isinstance(section, dict), f"Checklist '{key}' has non-object section.")
        section_name = str(section.get("name", "")).strip()
        _ensure(section_name, f"Checklist '{key}' has section with empty name.")
        items = section.get("items")
        _ensure(isinstance(items, list) and items, f"Checklist '{key}' section '{section_name}' has no items.")
        for item in items:
            _validate_item(key, section_name, item, seen_item_ids)


@lru_cache(maxsize=1)
def load_checklist_manifest():
    _ensure(MANIFEST_PATH.exists(), f"Checklist manifest not found: {MANIFEST_PATH}")
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    _ensure(isinstance(manifest, dict), "Checklist manifest must be an object.")
    checklists = manifest.get("checklists")
    _ensure(isinstance(checklists, list) and checklists, "Checklist manifest must contain a non-empty 'checklists' list.")

    seen_keys = set()
    seen_files = set()
    for entry in checklists:
        _ensure(isinstance(entry, dict), "Checklist manifest entries must be objects.")
        key = str(entry.get("key", "")).strip()
        filename = str(entry.get("file", "")).strip()
        _ensure(key, "Checklist manifest entry key is required.")
        _ensure(filename, f"Checklist manifest entry '{key}' file is required.")
        _ensure(key not in seen_keys, f"Duplicate checklist key in manifest: {key}")
        _ensure(filename not in seen_files, f"Duplicate checklist file in manifest: {filename}")
        seen_keys.add(key)
        seen_files.add(filename)
    return manifest


@lru_cache(maxsize=1)
def load_canonical_checklists():
    manifest = load_checklist_manifest()
    templates = []
    seen_template_keys = set()

    for entry in manifest["checklists"]:
        key = entry["key"]
        file_path = CHECKLISTS_DIR / entry["file"]
        _ensure(file_path.exists(), f"Checklist file not found for key '{key}': {file_path}")
        with file_path.open("r", encoding="utf-8") as f:
            template = json.load(f)

        _validate_template(template)

        template_key = str(template["key"]).strip()
        _ensure(template_key == key, f"Manifest key '{key}' does not match checklist file key '{template_key}'.")
        _ensure(template_key not in seen_template_keys, f"Duplicate checklist key loaded: {template_key}")
        seen_template_keys.add(template_key)

        templates.append(template)

    return tuple(templates)


def get_canonical_checklists():
    """Returns a deep-copy-safe list of canonical checklist templates."""
    return copy.deepcopy(list(load_canonical_checklists()))


def get_canonical_checklist_by_key(template_key):
    for template in load_canonical_checklists():
        if template["key"] == template_key:
            return copy.deepcopy(template)
    return None


def build_checklist_revision(template):
    payload = json.dumps(template, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_checklists_with_revisions():
    templates = get_canonical_checklists()
    for template in templates:
        template["system_revision"] = build_checklist_revision(template)
    return templates
