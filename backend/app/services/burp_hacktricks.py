import os
import re
from pathlib import Path
from typing import Dict, List

from app.config import BASE_DIR

_TOKEN = re.compile(r"[a-z0-9]{3,}")


def corpus_dir() -> Path:
    configured = str(os.getenv("HACKTRICKS_PATH") or "").strip()
    if configured:
        return Path(configured)
    return Path(BASE_DIR).resolve().parent / "scanner" / "knowledge" / "hacktricks-web"


def _iter_markdown(root: Path) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.md") if path.name.upper() != "NOTICE.MD")


def _chunks(text: str, size: int = 900) -> List[str]:
    cleaned = re.sub(r"\{\{[^}]+\}\}", "", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    parts: List[str] = []
    buf: List[str] = []
    count = 0
    for line in cleaned.splitlines():
        buf.append(line)
        count += len(line) + 1
        if count >= size:
            parts.append("\n".join(buf).strip())
            buf = []
            count = 0
    if buf:
        parts.append("\n".join(buf).strip())
    return [part for part in parts if len(part) > 40]


def search_hacktricks(query: str, limit: int = 5) -> List[Dict[str, str]]:
    terms = set(_TOKEN.findall(str(query or "").lower()))
    if not terms:
        return []
    scored: List[Dict[str, str]] = []
    root = corpus_dir()
    for path in _iter_markdown(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        for chunk in _chunks(text):
            lowered = chunk.lower()
            score = sum(1 for term in terms if term in lowered)
            if score <= 0:
                continue
            scored.append({"path": rel, "text": chunk[:1200], "score": str(score)})
    scored.sort(key=lambda item: (-int(item["score"]), item["path"]))
    out = []
    for item in scored[: max(1, min(int(limit), 5))]:
        out.append({"path": item["path"], "text": item["text"]})
    return out
