import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

ENROLL_PREFIX = "raptor_burp_enroll_"
AGENT_PREFIX = "raptor_burp_"
MAX_INGEST_EVENTS = 50
BODY_CAP = 16 * 1024
PAYLOAD_CAP = 200
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
STATIC_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
    ".webp",
}
SECRET_HEADERS = {
    "cookie",
    "set-cookie",
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "x-csrf-token",
}
CREDENTIAL_LABELS = ("username", "password", "user", "pass", "token")


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def normalize_host(value: str) -> str:
    host = str(value or "").strip().lower()
    if host.startswith("[") and "]" in host:
        host = host[1 : host.index("]")]
    if ":" in host and not host.count(":") > 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")


def normalize_path(value: str) -> str:
    path = str(value or "").strip() or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path.split("#", 1)[0] or "/"


def is_static_path(path: str) -> bool:
    cleaned = normalize_path(path).split("?", 1)[0].lower()
    for ext in STATIC_EXTENSIONS:
        if cleaned.endswith(ext):
            return True
    return False


def dedupe_key(tool: str, method: str, host: str, path: str, body: str) -> str:
    normalized_body = re.sub(r"\s+", " ", str(body or "")).strip()
    raw = "|".join(
        [
            str(tool or "").strip().lower(),
            str(method or "").strip().upper(),
            normalize_host(host),
            normalize_path(path).split("?", 1)[0],
            normalized_body,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_notes_credentials(notes: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for raw_line in str(notes or "").splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        key = label.strip().lower()
        if key in {"username", "user", "login"}:
            found["username"] = value.strip()
        elif key in {"password", "pass", "passwd"}:
            found["password"] = value.strip()
        elif key in {"token", "bearer", "jwt"}:
            found["token"] = value.strip()
    return found


def redact_headers(headers: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(headers, dict):
        items: Iterable[Tuple[Any, Any]] = headers.items()
    elif isinstance(headers, list):
        items = []
        for entry in headers:
            if isinstance(entry, dict) and "name" in entry:
                items.append((entry.get("name"), entry.get("value")))  # type: ignore[arg-type]
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                items.append((entry[0], entry[1]))
    else:
        return out
    for name, value in items:
        key = str(name or "").strip()
        if not key:
            continue
        if key.lower() in SECRET_HEADERS:
            out[key] = "[REDACTED]"
        else:
            out[key] = str(value or "")
    return out


def cap_body(body: Any) -> str:
    text = body if isinstance(body, str) else json.dumps(body) if body is not None else ""
    if len(text) > BODY_CAP:
        return text[:BODY_CAP]
    return text


def cap_payload(value: Any) -> str:
    text = strip_jwts(value if isinstance(value, str) else "" if value is None else str(value))
    return text[:PAYLOAD_CAP]


def strip_jwts(value: Any) -> str:
    return JWT_RE.sub("[jwt]", str(value or ""))


def jwt_present_in(*parts: Any) -> bool:
    for part in parts:
        if jwt_like(str(part or "")):
            return True
    return False


def as_json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return fallback
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) or fallback is None else fallback


def dump_json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, default=str)


def jwt_like(value: str) -> Optional[str]:
    match = JWT_RE.search(str(value or ""))
    return match.group(0) if match else None


def interesting_intruder(status: Optional[int], length: Optional[int], body: str, base_length: Optional[int]) -> bool:
    code = int(status or 0)
    if code >= 500:
        return True
    lowered = str(body or "").lower()
    if any(marker in lowered for marker in ("exception", "traceback", "sql syntax", "stack trace", "error")):
        return True
    if base_length is not None and length is not None and abs(int(length) - int(base_length)) >= 64:
        return True
    return False


MAX_ANALYZE_CLUSTERS = 40


def cluster_key(row: Dict[str, Any]) -> Tuple[str, str, str, str]:
    tool = str(row.get("tool") or "").strip().lower() or "repeater"
    host = normalize_host(str(row.get("host") or ""))
    method = str(row.get("method") or "GET").strip().upper() or "GET"
    path = normalize_path(str(row.get("path") or "/")).split("?", 1)[0]
    return tool, host, method, path


def _as_status(value: Any) -> Optional[int]:
    try:
        if value is None or str(value) == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _excerpt(row: Dict[str, Any]) -> Dict[str, Any]:
    blob = row.get("excerpt_json")
    return blob if isinstance(blob, dict) else {}


def event_fingerprint(rows: List[Dict[str, Any]]) -> str:
    parts = []
    for row in sorted(rows or [], key=lambda item: int(item.get("id") or 0)):
        parts.append(
            f"{int(row.get('id') or 0)}:{int(row.get('count') or 1)}:{row.get('status') if row.get('status') is not None else ''}"
        )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def cluster_events(rows: List[Dict[str, Any]], limit: int = MAX_ANALYZE_CLUSTERS) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for row in rows or []:
        tool, host, method, path = cluster_key(row)
        key = (tool, host, method, path)
        bucket = groups.get(key)
        if bucket is None:
            bucket = {
                "tool": tool,
                "host": host,
                "method": method,
                "path": path,
                "tools": set(),
                "count": 0,
                "statuses": {},
                "sample_ids": [],
                "flags": set(),
            }
            groups[key] = bucket
        count = int(row.get("count") or 1)
        bucket["count"] += count
        if tool:
            bucket["tools"].add(tool)
        status_i = _as_status(row.get("status"))
        if status_i is not None:
            label = str(status_i)
            bucket["statuses"][label] = int(bucket["statuses"].get(label) or 0) + count
            if status_i >= 500:
                bucket["flags"].add("5xx")
            if status_i in {401, 403}:
                bucket["flags"].add("auth")
        if row.get("scanner_name"):
            bucket["flags"].add("scanner")
        event_id = row.get("id")
        if event_id is not None and len(bucket["sample_ids"]) < 3:
            bucket["sample_ids"].append(int(event_id))
    clusters = []
    for bucket in groups.values():
        clusters.append(
            {
                "tool": bucket["tool"],
                "host": bucket["host"],
                "method": bucket["method"],
                "path": bucket["path"],
                "tools": sorted(bucket["tools"]),
                "count": int(bucket["count"]),
                "statuses": dict(sorted(bucket["statuses"].items(), key=lambda item: int(item[0]))),
                "sample_ids": bucket["sample_ids"],
                "flags": sorted(bucket["flags"]),
            }
        )
    clusters.sort(
        key=lambda item: (-int(item["count"]), item["tool"], item["host"], item["method"], item["path"])
    )
    return clusters[: max(1, int(limit or MAX_ANALYZE_CLUSTERS))]


def pick_best_event(group: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not group:
        return None
    statuses = {_as_status(row.get("status")) for row in group}
    statuses.discard(None)
    has_auth = any(code in {401, 403} for code in statuses)
    has_2xx = any(200 <= int(code) < 300 for code in statuses)

    def _id(row: Dict[str, Any]) -> int:
        return int(row.get("id") or 0)

    with_body = [
        row
        for row in group
        if str(row.get("tool") or "").lower() == "repeater"
        and str(_excerpt(row).get("response_body") or "").strip()
    ]
    if with_body:
        return max(with_body, key=_id)
    if has_auth and has_2xx:
        flipped = [
            row
            for row in group
            if (code := _as_status(row.get("status"))) is not None and 200 <= code < 300
        ]
        if flipped:
            return max(flipped, key=_id)
    fivexx = [
        row
        for row in group
        if (code := _as_status(row.get("status"))) is not None and code >= 500
    ]
    if fivexx:
        return max(fivexx, key=_id)
    return max(group, key=_id)


def serialize_best(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    excerpt = _excerpt(row)
    return {
        "id": int(row.get("id") or 0),
        "tool": str(row.get("tool") or ""),
        "method": str(row.get("method") or ""),
        "host": str(row.get("host") or ""),
        "path": str(row.get("path") or ""),
        "status": row.get("status"),
        "query": str(excerpt.get("query") or ""),
        "headers": excerpt.get("headers") if isinstance(excerpt.get("headers"), dict) else {},
        "body": str(excerpt.get("body") or ""),
        "response_headers": excerpt.get("response_headers")
        if isinstance(excerpt.get("response_headers"), dict)
        else {},
        "response_body": str(excerpt.get("response_body") or ""),
        "payload": str(excerpt.get("payload") or ""),
        "jwt_present": bool(excerpt.get("jwt_present")),
    }


def enrich_clusters(
    rows: List[Dict[str, Any]],
    clusters: Optional[List[Dict[str, Any]]] = None,
    limit: int = MAX_ANALYZE_CLUSTERS,
) -> List[Dict[str, Any]]:
    members: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    for row in rows or []:
        members.setdefault(cluster_key(row), []).append(row)
    base = clusters if clusters is not None else cluster_events(rows, limit=limit)
    enriched = []
    for cluster in base:
        key = (
            str(cluster.get("tool") or "").strip().lower() or "repeater",
            str(cluster.get("host") or ""),
            str(cluster.get("method") or "GET").strip().upper() or "GET",
            str(cluster.get("path") or "/"),
        )
        group = members.get(key, [])
        excerpt_jwt = False
        lengths: List[int] = []
        scanner_name = ""
        scanner_severity = ""
        scanner_confidence = ""
        statuses = set()
        for row in group:
            status_i = _as_status(row.get("status"))
            if status_i is not None:
                statuses.add(status_i)
            excerpt = _excerpt(row)
            if excerpt.get("jwt_present"):
                excerpt_jwt = True
            try:
                if excerpt.get("length") is not None:
                    lengths.append(int(excerpt.get("length")))
            except (TypeError, ValueError):
                pass
            if row.get("scanner_name") and not scanner_name:
                scanner_name = str(row.get("scanner_name") or "")
                scanner_severity = str(row.get("scanner_severity") or "")
                scanner_confidence = str(row.get("scanner_confidence") or "")
        has_2xx = any(200 <= code < 300 for code in statuses)
        deltas: List[str] = []
        if 401 in statuses and has_2xx:
            deltas.append("401→200")
        if 403 in statuses and has_2xx:
            deltas.append("403→200")
        if any(code >= 500 for code in statuses):
            deltas.append("5xx")
        if lengths and (max(lengths) - min(lengths) >= 64):
            deltas.append("length")
        if excerpt_jwt:
            deltas.append("jwt")
        best = serialize_best(pick_best_event(group))
        scanner_row = next(
            (
                row
                for row in sorted(group, key=lambda item: int(item.get("id") or 0), reverse=True)
                if row.get("scanner_name")
            ),
            None,
        )
        payload = str((best or {}).get("payload") or "")
        enriched.append(
            {
                **cluster,
                "deltas": deltas,
                "jwt_present": excerpt_jwt,
                "payload": payload,
                "scanner_name": scanner_name,
                "scanner_severity": scanner_severity,
                "scanner_confidence": scanner_confidence,
                "scanner_event_id": int(scanner_row["id"]) if scanner_row and scanner_row.get("id") is not None else None,
                "best": best,
            }
        )
    return enriched


def index_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "tool": row.get("tool") or "",
        "method": row.get("method") or "",
        "host": row.get("host") or "",
        "path": row.get("path") or "",
        "status": row.get("status"),
        "count": int(row.get("count") or 1),
        "issue_name": row.get("scanner_name") or "",
        "severity": row.get("scanner_severity") or "",
    }
