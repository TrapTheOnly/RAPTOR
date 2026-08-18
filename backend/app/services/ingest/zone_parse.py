"""BIND-style zone text parser used by the bind_file compatibility adapter."""

import re
from typing import Iterable, List, Optional, Tuple

from app.services.ingest.fqdn import normalize_fqdn
from app.services.ingest.models import ResourceRecord

_TTL_RE = re.compile(r"^(\d+)([smhdw])?$", re.IGNORECASE)
_CLASS_TOKENS = {"IN", "CH", "HS"}
_PROJECTABLE_TYPES = {"A"}
_KEEP_TYPES = {"A", "AAAA", "CNAME", "TXT", "MX", "NS", "SOA"}


def parse_ttl_token(token: str) -> Optional[int]:
    match = _TTL_RE.match(str(token or "").strip())
    if not match:
        return None
    value = int(match.group(1))
    unit = (match.group(2) or "").lower()
    multipliers = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return value * multipliers[unit]


def _strip_comment(line: str) -> str:
    in_quote = False
    chars: List[str] = []
    for char in line:
        if char == '"':
            in_quote = not in_quote
            chars.append(char)
            continue
        if char == ";" and not in_quote:
            break
        chars.append(char)
    return "".join(chars).rstrip()


def unfold_zone_text(text: str) -> List[str]:
    depth = 0
    buf: List[str] = []
    lines: List[str] = []
    for raw in str(text or "").splitlines():
        stripped = _strip_comment(raw)
        if not stripped.strip() and depth == 0:
            continue
        depth += stripped.count("(") - stripped.count(")")
        buf.append(stripped.replace("(", " ").replace(")", " "))
        if depth <= 0:
            joined = " ".join(part.strip() for part in buf if part.strip())
            if joined:
                lines.append(joined)
            buf = []
            depth = 0
    if buf:
        joined = " ".join(part.strip() for part in buf if part.strip())
        if joined:
            lines.append(joined)
    return lines


def _split_tokens(line: str) -> List[str]:
    return [token for token in re.findall(r'"[^"]*"|[^\s]+', line) if token]


def parse_zone_records(text: str, origin: str) -> List[ResourceRecord]:
    current_origin = normalize_fqdn(origin)
    default_ttl: Optional[int] = None
    last_owner = ""
    records: List[ResourceRecord] = []

    for line in unfold_zone_text(text):
        if line.upper().startswith("$ORIGIN"):
            parts = line.split(None, 1)
            if len(parts) == 2:
                current_origin = normalize_fqdn(parts[1], current_origin)
                last_owner = current_origin
            continue
        if line.upper().startswith("$TTL"):
            parts = line.split(None, 1)
            if len(parts) == 2:
                default_ttl = parse_ttl_token(parts[1].split()[0])
            continue
        if line.upper().startswith("$"):
            continue

        tokens = _split_tokens(line)
        if not tokens:
            continue

        owner = last_owner
        idx = 0
        ttl = default_ttl
        if tokens[0].upper() not in _CLASS_TOKENS and parse_ttl_token(tokens[0]) is None:
            maybe_type = tokens[0].upper().strip('"')
            if maybe_type not in _KEEP_TYPES:
                owner_token = tokens[0]
                if owner_token == "@" or owner_token:
                    owner = normalize_fqdn(owner_token, current_origin)
                idx = 1

        if idx < len(tokens):
            parsed_ttl = parse_ttl_token(tokens[idx])
            if parsed_ttl is not None:
                ttl = parsed_ttl
                idx += 1
        if idx < len(tokens) and tokens[idx].upper() in _CLASS_TOKENS:
            idx += 1
        if idx >= len(tokens):
            continue

        rrtype = tokens[idx].upper().strip('"')
        idx += 1
        if rrtype not in _KEEP_TYPES or idx > len(tokens):
            last_owner = owner or last_owner
            continue

        rdata = " ".join(token.strip('"') for token in tokens[idx:]).strip()
        fqdn = owner or last_owner or current_origin
        if not fqdn or not rdata:
            last_owner = owner or last_owner
            continue
        records.append(
            ResourceRecord(
                fqdn=fqdn,
                rrtype=rrtype,
                rdata=rdata,
                ttl=ttl,
                zone=current_origin,
            )
        )
        last_owner = fqdn

    return records


def soa_serial_from_records(records: Iterable[ResourceRecord]) -> Optional[str]:
    for record in records:
        if record.rrtype != "SOA":
            continue
        parts = str(record.rdata or "").split()
        if len(parts) >= 3 and parts[2].isdigit():
            return parts[2]
    return None


def a_records_as_hosts(records: Iterable[ResourceRecord]) -> List[dict]:
    hosts = []
    seen = set()
    for record in records:
        if record.rrtype not in _PROJECTABLE_TYPES:
            continue
        key = record.fqdn
        if key in seen:
            continue
        seen.add(key)
        hosts.append({"name": record.fqdn, "ip_address": record.rdata})
    return hosts


def parse_bind_zone_file(filepath: str, origin: str) -> Tuple[List[ResourceRecord], List[dict]]:
    with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    records = parse_zone_records(text, origin)
    return records, a_records_as_hosts(records)
