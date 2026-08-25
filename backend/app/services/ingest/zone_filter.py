from typing import Iterable, List, Mapping, Optional

from app.services.ingest.models import ZoneSnapshot


def _norm_tokens(values: Optional[Iterable[str]]) -> List[str]:
    tokens = []
    for value in values or []:
        token = str(value or "").strip().lower().rstrip(".")
        if token:
            tokens.append(token)
    return tokens


def zone_allowed(snapshot: ZoneSnapshot, config: Optional[Mapping] = None) -> bool:
    cfg = dict(config or {})
    allow = _norm_tokens(cfg.get("zone_allowlist") or cfg.get("zones") or [])
    deny = _norm_tokens(cfg.get("zone_denylist") or [])
    name = str(snapshot.name or "").strip().lower().rstrip(".")
    zone_id = str(snapshot.provider_zone_id or "").strip().lower()
    tokens = {token for token in (name, zone_id) if token}
    if deny and tokens.intersection(deny):
        return False
    if allow and not tokens.intersection(allow):
        return False
    return True
