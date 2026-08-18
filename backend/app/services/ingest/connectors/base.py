from typing import Iterable, List, Protocol

from app.services.ingest.models import ResourceRecord, ZoneSnapshot


class DnsConnector(Protocol):
    def list_zones(self) -> List[ZoneSnapshot]:
        ...

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        ...
