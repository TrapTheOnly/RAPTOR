from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ResourceRecord:
    fqdn: str
    rrtype: str
    rdata: str
    ttl: Optional[int] = None
    zone: str = ""
    provider_zone_id: Optional[str] = None
    provider_record_id: Optional[str] = None


@dataclass(frozen=True)
class ZoneSnapshot:
    name: str
    soa_serial: Optional[str] = None
    records: Optional[List[ResourceRecord]] = None
    provider_zone_id: Optional[str] = None
