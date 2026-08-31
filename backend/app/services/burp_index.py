import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import DATA_PATH
from app.domain.burp.fields import index_entry
from app.repositories import burp_repository


def index_dir(wave_id: int) -> Path:
    return Path(DATA_PATH) / "burp" / str(int(wave_id))


def index_path(wave_id: int) -> Path:
    return index_dir(wave_id) / "index.json"


def rewrite_index(wave_id: int) -> Dict[str, Any]:
    rows = burp_repository.list_events_for_wave(int(wave_id), limit=500)
    payload = {
        "wave_id": int(wave_id),
        "event_count": len(rows),
        "events": [index_entry(row) for row in rows],
    }
    dest = index_path(wave_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, dest)
    return payload


def read_index(wave_id: int) -> Dict[str, Any]:
    path = index_path(wave_id)
    if not path.is_file():
        return rewrite_index(wave_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return rewrite_index(wave_id)


def burp_get(event_id: int, wave_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    row = burp_repository.get_event(int(event_id), wave_id=wave_id)
    if not row:
        return None
    excerpt = row.get("excerpt_json") if isinstance(row.get("excerpt_json"), dict) else {}
    return {
        "id": row.get("id"),
        "tool": row.get("tool"),
        "method": row.get("method"),
        "host": row.get("host"),
        "path": row.get("path"),
        "status": row.get("status"),
        "count": row.get("count"),
        "headers": excerpt.get("headers") or {},
        "body": excerpt.get("body") or "",
        "query": excerpt.get("query") or "",
        "length": excerpt.get("length"),
        "scanner": {
            "type": row.get("scanner_type") or "",
            "name": row.get("scanner_name") or "",
            "severity": row.get("scanner_severity") or "",
            "confidence": row.get("scanner_confidence") or "",
            "parameter": row.get("scanner_parameter") or "",
            "detail": row.get("scanner_detail") or "",
        },
    }


def burp_search(
    wave_id: int,
    *,
    path_prefix: str = "",
    issue_name: str = "",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    return burp_repository.search_events(
        int(wave_id),
        path_prefix=path_prefix,
        issue_name=issue_name,
        limit=limit,
    )
