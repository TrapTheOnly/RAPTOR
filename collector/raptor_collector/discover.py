"""Discover BIND, PowerDNS, and Windows DNS zone sources on this host."""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from raptor_collector.named_conf import load_bind_zones
from raptor_collector.zone import ResourceRecord, parse_zone_records, soa_serial

logger = logging.getLogger(__name__)

BIND_CONF_CANDIDATES = (
    "/etc/bind/named.conf",
    "/etc/named.conf",
    "/etc/named/named.conf",
    "/chroot/etc/named.conf",
)
POWERDNS_CONF_CANDIDATES = (
    "/etc/powerdns/pdns.conf",
    "/etc/pdns/pdns.conf",
)


@dataclass
class DiscoveredZone:
    name: str
    source: str
    file_path: Optional[str] = None
    soa_serial: Optional[str] = None
    records: List[ResourceRecord] = field(default_factory=list)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _load_zone_file(path: str, origin: str) -> List[ResourceRecord]:
    try:
        return parse_zone_records(_read_text(path), origin)
    except OSError as exc:
        logger.warning("Failed to read zone file %s: %s", path, exc)
        return []


def discover_bind(conf_path: str = "") -> List[DiscoveredZone]:
    candidates = (conf_path,) if conf_path else BIND_CONF_CANDIDATES
    found: List[DiscoveredZone] = []
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        for zone in load_bind_zones(path):
            records = _load_zone_file(zone.file_path, zone.name) if zone.file_path else []
            found.append(
                DiscoveredZone(
                    name=zone.name,
                    source="bind",
                    file_path=zone.file_path,
                    soa_serial=soa_serial(records),
                    records=records,
                )
            )
        if found:
            break
    return found


def _parse_pdns_conf(path: str) -> dict:
    config = {}
    try:
        for line in _read_text(path).splitlines():
            stripped = line.split("#", 1)[0].strip()
            if not stripped or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            config[key.strip()] = value.strip()
    except OSError:
        return {}
    return config


def discover_powerdns(conf_path: str = "") -> List[DiscoveredZone]:
    path = conf_path or next((item for item in POWERDNS_CONF_CANDIDATES if os.path.isfile(item)), "")
    if not path:
        return []
    config = _parse_pdns_conf(path)
    bind_config = config.get("bind-config") or config.get("bind-config-file")
    zones: List[DiscoveredZone] = []
    if bind_config and os.path.isfile(bind_config):
        for zone in load_bind_zones(bind_config):
            records = _load_zone_file(zone.file_path, zone.name) if zone.file_path else []
            zones.append(
                DiscoveredZone(
                    name=zone.name,
                    source="powerdns",
                    file_path=zone.file_path,
                    soa_serial=soa_serial(records),
                    records=records,
                )
            )
        if zones:
            return zones

    pdnsutil = shutil.which("pdnsutil")
    if not pdnsutil:
        return zones
    try:
        listed = subprocess.run(
            [pdnsutil, "list-all-zones"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("pdnsutil list-all-zones failed: %s", exc)
        return zones
    if listed.returncode != 0:
        return zones
    for line in listed.stdout.splitlines():
        name = line.strip().rstrip(".").lower()
        if not name:
            continue
        zones.append(DiscoveredZone(name=name, source="powerdns"))
    return zones


def discover_windows_dns() -> List[DiscoveredZone]:
    if os.name != "nt":
        return []
    dnscmd = shutil.which("dnscmd")
    if not dnscmd:
        return []
    try:
        listed = subprocess.run(
            [dnscmd, ".", "/EnumZones"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("dnscmd /EnumZones failed: %s", exc)
        return []
    zones: List[DiscoveredZone] = []
    for line in listed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0].lower() in {"zone name", "zone"}:
            continue
        name = parts[0].strip().rstrip(".").lower()
        if "." not in name and name in {".", "enumzones", "command"}:
            continue
        if name:
            zones.append(DiscoveredZone(name=name, source="windows_dns"))
    return zones


def discover_zone_dirs(directories: Iterable[str]) -> List[DiscoveredZone]:
    found: List[DiscoveredZone] = []
    for directory in directories:
        if not directory or not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            origin = name
            if origin.endswith(".db"):
                origin = origin[:-3]
            origin = origin.rstrip(".").lower()
            records = _load_zone_file(path, origin)
            found.append(
                DiscoveredZone(
                    name=origin,
                    source="zone_dir",
                    file_path=path,
                    soa_serial=soa_serial(records),
                    records=records,
                )
            )
    return found


def discover_all(
    *,
    bind_conf: str = "",
    powerdns_conf: str = "",
    extra_zone_dirs: Optional[Iterable[str]] = None,
) -> List[DiscoveredZone]:
    discovered: List[DiscoveredZone] = []
    discovered.extend(discover_bind(bind_conf))
    discovered.extend(discover_powerdns(powerdns_conf))
    discovered.extend(discover_windows_dns())
    discovered.extend(discover_zone_dirs(extra_zone_dirs or ()))
    by_name = {}
    for zone in discovered:
        if zone.name and zone.name not in by_name:
            by_name[zone.name] = zone
    return list(by_name.values())
