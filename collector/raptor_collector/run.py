import json
import logging
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from raptor_collector import __version__
from raptor_collector.axfr import axfr_zone
from raptor_collector.client import CollectorClient
from raptor_collector.config import CollectorConfig
from raptor_collector.discover import DiscoveredZone, discover_all
from raptor_collector.zone import records_to_payload, soa_serial

logger = logging.getLogger(__name__)


def load_state(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _fill_from_axfr(zone: DiscoveredZone, config: CollectorConfig) -> DiscoveredZone:
    if zone.records or not config.axfr_server:
        return zone
    try:
        records = axfr_zone(
            zone.name,
            config.axfr_server,
            tsig_name=config.tsig_name,
            tsig_secret=config.tsig_secret,
            tsig_algorithm=config.tsig_algorithm,
        )
    except Exception as exc:
        logger.warning("AXFR failed for %s: %s", zone.name, exc)
        return zone
    zone.records = records
    zone.soa_serial = soa_serial(records)
    return zone


def collect_zones(config: CollectorConfig) -> List[DiscoveredZone]:
    discovered = discover_all(
        bind_conf=config.bind_conf,
        powerdns_conf=config.powerdns_conf,
        extra_zone_dirs=config.extra_zone_dirs,
    )
    return [_fill_from_axfr(zone, config) for zone in discovered]


def zones_payload(zones: List[DiscoveredZone]) -> List[Dict[str, Any]]:
    payload = []
    for zone in zones:
        payload.append(
            {
                "name": zone.name,
                "soa_serial": zone.soa_serial or "",
                "records": records_to_payload(zone.records),
            }
        )
    return payload


def enroll(config: CollectorConfig, enroll_token: Optional[str] = None) -> Dict[str, Any]:
    token = enroll_token or config.enroll_token
    if not config.raptor_url:
        raise RuntimeError("RAPTOR_URL is required")
    if not token:
        raise RuntimeError("Enroll token is required")
    client = CollectorClient(config.raptor_url)
    result = client.enroll(token, config.hostname or socket.gethostname(), __version__)
    state = load_state(config.state_path)
    state.update(
        {
            "token": result.get("token"),
            "source_id": result.get("source_id"),
            "agent_id": result.get("agent_id"),
            "hostname": result.get("hostname") or config.hostname,
            "raptor_url": config.raptor_url,
        }
    )
    save_state(config.state_path, state)
    logger.info("Enrolled collector source_id=%s agent_id=%s", state.get("source_id"), state.get("agent_id"))
    return state


def _client_from_state(config: CollectorConfig) -> tuple[CollectorClient, Dict[str, Any]]:
    state = load_state(config.state_path)
    token = config.token or str(state.get("token") or "")
    url = config.raptor_url or str(state.get("raptor_url") or "")
    if not url or not token:
        raise RuntimeError("Collector is not enrolled. Run `raptor-collector enroll` first.")
    client = CollectorClient(url, token=token)
    return client, state


def persist_rotated_token(config: CollectorConfig, state: Dict[str, Any], response: Dict[str, Any]) -> None:
    if response.get("token"):
        state["token"] = response["token"]
        save_state(config.state_path, state)


def run_once(config: CollectorConfig) -> Dict[str, Any]:
    if not load_state(config.state_path).get("token") and (config.enroll_token or "").strip():
        enroll(config)
    client, state = _client_from_state(config)
    zones = collect_zones(config)
    summaries = [{"name": zone.name, "soa_serial": zone.soa_serial or ""} for zone in zones]
    heartbeat = client.heartbeat(summaries, __version__, soa_serial=summaries[0]["soa_serial"] if summaries else "")
    persist_rotated_token(config, state, heartbeat)
    ingestable = [zone for zone in zones if zone.records]
    if not ingestable:
        logger.warning("No zone records collected on this host")
        return {"heartbeat": heartbeat, "ingest": None, "zones": summaries}
    source_id = int(state.get("source_id") or heartbeat.get("source_id") or 0)
    ingest = client.ingest(
        source_id,
        zones_payload(ingestable),
        __version__,
        cursor=summaries[0]["soa_serial"] if summaries else "",
    )
    persist_rotated_token(config, state, ingest)
    logger.info(
        "Ingested %s zones stored=%s projected=%s",
        len(ingestable),
        ingest.get("stored"),
        ingest.get("projected"),
    )
    return {"heartbeat": heartbeat, "ingest": ingest, "zones": summaries}


def run_loop(config: CollectorConfig) -> None:
    while True:
        try:
            run_once(config)
        except Exception as exc:
            logger.error("Collector cycle failed: %s", exc)
        time.sleep(config.interval_seconds)
