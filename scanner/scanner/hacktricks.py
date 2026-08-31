"""Retrieval over the vendored HackTricks web tree. Never dump the wiki into a prompt."""

from __future__ import annotations

import os
import re
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]{3,}")


def corpus_dir() -> Path:
    configured = str(os.getenv("HACKTRICKS_PATH") or "").strip()
    if configured:
        return Path(configured)
    here = Path(__file__).resolve()
    return here.parents[1] / "knowledge" / "hacktricks-web"


def search_hacktricks(query: str, limit: int = 5) -> list[dict[str, str]]:
    terms = set(_TOKEN.findall(str(query or "").lower()))
    if not terms:
        return []
    root = corpus_dir()
    if not root.is_dir():
        return []
    scored: list[tuple[int, str, str]] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.upper() == "NOTICE.MD":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        cleaned = re.sub(r"\{\{[^}]+\}\}", "", text)
        for chunk in _chunks(cleaned):
            score = sum(1 for term in terms if term in chunk.lower())
            if score:
                scored.append((score, str(path.relative_to(root)), chunk[:1200]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [{"path": path, "text": text} for _, path, text in scored[: max(1, min(int(limit), 5))]]


def _chunks(text: str, size: int = 900) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    count = 0
    for line in text.splitlines():
        buf.append(line)
        count += len(line) + 1
        if count >= size:
            joined = "\n".join(buf).strip()
            if len(joined) > 40:
                parts.append(joined)
            buf = []
            count = 0
    if buf:
        joined = "\n".join(buf).strip()
        if len(joined) > 40:
            parts.append(joined)
    return parts
