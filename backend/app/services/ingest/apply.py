import ipaddress
import logging
import uuid
from typing import Any, Dict, Iterable, List, Optional

from app.repositories.dns_sources_repository import get_dns_source, record_observations
from app.repositories.ip_sources_repository import ensure_ip_sources, ip_source_name_for_dns_type
from app.repositories.records_repository import determine_source, store_records_in_db
from app.services.ingest.models import ResourceRecord
from app.services.ingest.zone_parse import a_records_as_hosts

logger = logging.getLogger(__name__)

PROJECTABLE_RRTYPES = {"A"}


def _as_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_ipv4(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(str(value or "").strip()), ipaddress.IPv4Address)
    except ValueError:
        return False


def _as_resource_record(item: Any) -> Optional[ResourceRecord]:
    if isinstance(item, ResourceRecord):
        return item
    if not isinstance(item, dict):
        return None
    fqdn = str(item.get("fqdn") or item.get("name") or "").strip().lower().rstrip(".")
    rrtype = str(item.get("rrtype") or "A").strip().upper()
    rdata = str(item.get("rdata") if item.get("rdata") is not None else item.get("ip_address") or "").strip()
    if not fqdn or not rdata:
        return None
    ttl = _as_int(item.get("ttl"))
    zone = str(item.get("zone") or "").strip().lower().rstrip(".")
    provider_zone_id = str(item.get("provider_zone_id") or "").strip() or None
    provider_record_id = str(item.get("provider_record_id") or "").strip() or None
    return ResourceRecord(
        fqdn=fqdn,
        rrtype=rrtype,
        rdata=rdata,
        ttl=ttl,
        zone=zone,
        provider_zone_id=provider_zone_id,
        provider_record_id=provider_record_id,
    )


def project_a_records(
    records: Iterable[Any],
    *,
    ip_source_name: Optional[str] = None,
) -> List[Dict[str, str]]:
    parsed = [record for record in (_as_resource_record(item) for item in records) if record]
    projectable = [
        record
        for record in parsed
        if record.rrtype in PROJECTABLE_RRTYPES and is_ipv4(record.rdata)
    ]
    hosts = a_records_as_hosts(projectable)
    label = str(ip_source_name or "").strip()
    for host in hosts:
        host["source"] = label or determine_source(host["ip_address"])
    return hosts


def apply_ingest_batch(
    source_id: int,
    records: Iterable[Any],
    *,
    batch_id: Optional[str] = None,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """Store all RRs as observations; project A records onto the attack-surface table."""
    parsed = [record for record in (_as_resource_record(item) for item in records) if record]
    if not parsed:
        return {"stored": 0, "projected": 0, "batch_id": batch_id or ""}

    resolved_batch_id = batch_id or str(uuid.uuid4())
    observation_rows = [
        {
            "name": record.fqdn,
            "fqdn": record.fqdn,
            "rrtype": record.rrtype,
            "rdata": record.rdata,
            "ip_address": record.rdata if record.rrtype == "A" else "",
            "ttl": record.ttl,
            "zone": record.zone,
            "provider_zone_id": record.provider_zone_id,
            "provider_record_id": record.provider_record_id,
        }
        for record in parsed
    ]
    record_observations(
        source_id,
        observation_rows,
        resolved_batch_id,
        cursor_value=cursor or resolved_batch_id,
    )
    dns_source = get_dns_source(source_id, mask=True)
    ip_source_name = ip_source_name_for_dns_type((dns_source or {}).get("type"))
    projected = project_a_records(parsed, ip_source_name=ip_source_name)
    if projected and ip_source_name:
        ensure_ip_sources(ip_source_name, [host["ip_address"] for host in projected])
    if projected:
        store_records_in_db(projected, source_id=source_id)
    logger.info(
        "Ingest batch %s source=%s stored=%s projected=%s",
        resolved_batch_id,
        source_id,
        len(parsed),
        len(projected),
    )
    return {
        "stored": len(parsed),
        "projected": len(projected),
        "batch_id": resolved_batch_id,
    }
