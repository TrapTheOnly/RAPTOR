"""Parse named.conf zone statements and includes."""

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set


@dataclass(frozen=True)
class BindZone:
    name: str
    file_path: Optional[str]
    zone_type: str = ""


_ZONE_RE = re.compile(
    r'zone\s+"([^"]+)"\s*(?:in\s+)?\{(.*?)\};',
    re.IGNORECASE | re.DOTALL,
)
_FILE_RE = re.compile(r'\bfile\s+"([^"]+)"', re.IGNORECASE)
_TYPE_RE = re.compile(r'\btype\s+(\w+)', re.IGNORECASE)
_INCLUDE_RE = re.compile(r'\binclude\s+"([^"]+)"\s*;', re.IGNORECASE)


def _strip_named_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"#.*?$", " ", text, flags=re.MULTILINE)
    return text


def parse_named_conf(text: str, conf_dir: str = "") -> List[BindZone]:
    cleaned = _strip_named_comments(text)
    zones: List[BindZone] = []
    for match in _ZONE_RE.finditer(cleaned):
        name = match.group(1).strip().rstrip(".").lower()
        body = match.group(2)
        file_match = _FILE_RE.search(body)
        type_match = _TYPE_RE.search(body)
        file_path = file_match.group(1) if file_match else None
        if file_path and not os.path.isabs(file_path) and conf_dir:
            file_path = os.path.normpath(os.path.join(conf_dir, file_path))
        zones.append(
            BindZone(
                name=name,
                file_path=file_path,
                zone_type=(type_match.group(1).lower() if type_match else ""),
            )
        )
    return zones


def iter_named_conf_files(path: str, seen: Optional[Set[str]] = None) -> Iterable[str]:
    seen = seen if seen is not None else set()
    resolved = os.path.abspath(path)
    if resolved in seen or not os.path.isfile(resolved):
        return
    seen.add(resolved)
    yield resolved
    directory = os.path.dirname(resolved)
    try:
        text = open(resolved, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return
    for match in _INCLUDE_RE.finditer(_strip_named_comments(text)):
        included = match.group(1)
        if not os.path.isabs(included):
            included = os.path.join(directory, included)
        yield from iter_named_conf_files(included, seen)


def load_bind_zones(conf_path: str) -> List[BindZone]:
    zones: List[BindZone] = []
    for path in iter_named_conf_files(conf_path):
        directory = os.path.dirname(path)
        try:
            text = open(path, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        zones.extend(parse_named_conf(text, directory))
    return zones
