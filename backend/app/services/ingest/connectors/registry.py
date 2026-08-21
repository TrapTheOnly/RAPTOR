from typing import Iterable, List, Mapping, Optional

from app.services.ingest.connectors.alidns import AliDnsConnector
from app.services.ingest.connectors.azure import AzureDnsConnector
from app.services.ingest.connectors.base import DnsConnector
from app.services.ingest.connectors.cloudflare import CloudflareConnector
from app.services.ingest.connectors.gcp import GcpDnsConnector
from app.services.ingest.connectors.route53 import Route53Connector
from app.services.ingest.models import ResourceRecord, ZoneSnapshot

PULL_CONNECTOR_TYPES = ("cloudflare", "route53", "alidns", "azure", "gcp")


def build_connector(source_type: str, config: Optional[Mapping] = None) -> DnsConnector:
    kind = str(source_type or "").strip().lower()
    cfg = dict(config or {})
    if kind == "cloudflare":
        return CloudflareConnector(cfg)
    if kind == "route53":
        return Route53Connector(cfg)
    if kind == "alidns":
        return AliDnsConnector(cfg)
    if kind == "azure":
        return AzureDnsConnector(cfg)
    if kind == "gcp":
        return GcpDnsConnector(cfg)
    raise ValueError(f"Unsupported DNS source type: {source_type}")


def fetch_all_records(connector: DnsConnector) -> List[ResourceRecord]:
    fetch_all = getattr(connector, "fetch_all", None)
    if callable(fetch_all):
        return list(fetch_all())
    records: List[ResourceRecord] = []
    zones: Iterable[ZoneSnapshot] = connector.list_zones()
    for snapshot in zones:
        records.extend(list(connector.fetch_records(snapshot.name)))
    return records
