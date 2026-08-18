"""Compatibility adapter: glob SHARED_PATH/*_A_Records until collectors replace it."""

import glob
import os
from typing import Iterable, List

from app.config import DATA_PATH, SHARED_PATH
from app.services.ingest.models import ResourceRecord, ZoneSnapshot
from app.services.ingest.zone_parse import parse_bind_zone_file, soa_serial_from_records


class BindFileConnector:
    def __init__(self, shared_path: str = SHARED_PATH, data_path: str = DATA_PATH) -> None:
        self.shared_path = shared_path
        self.data_path = data_path

    def list_zones(self) -> List[ZoneSnapshot]:
        from app.services.dns_sync_service import extract_domain_from_filename

        snapshots: List[ZoneSnapshot] = []
        for zone_file in glob.glob(os.path.join(self.shared_path, "*_A_Records")):
            origin = extract_domain_from_filename(zone_file)
            if not origin:
                continue
            snapshots.append(ZoneSnapshot(name=origin, records=None, soa_serial=None))
        return snapshots

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        from app.services.dns_sync_service import handle_zone_file_changes

        matches = glob.glob(os.path.join(self.shared_path, f"{zone}_A_Records"))
        if not matches:
            return []
        live_path = os.path.join(self.data_path, os.path.basename(matches[0]))
        final_path = handle_zone_file_changes(matches[0], live_path)
        if not final_path:
            return []
        records, _hosts = parse_bind_zone_file(final_path, zone)
        return records

    def fetch_all(self) -> List[ResourceRecord]:
        records: List[ResourceRecord] = []
        for snapshot in self.list_zones():
            records.extend(list(self.fetch_records(snapshot.name)))
        return records

    def soa_serial(self, records: Iterable[ResourceRecord]) -> str:
        return soa_serial_from_records(records) or ""
