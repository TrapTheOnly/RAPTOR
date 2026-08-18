import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name) or default).strip()


@dataclass
class CollectorConfig:
    raptor_url: str
    token: str
    enroll_token: str
    hostname: str
    state_path: Path
    bind_conf: str
    powerdns_conf: str
    axfr_server: str
    tsig_name: str
    tsig_secret: str
    tsig_algorithm: str
    interval_seconds: int
    extra_zone_dirs: tuple

    @classmethod
    def from_env(cls) -> "CollectorConfig":
        hostname = _env("RAPTOR_COLLECTOR_HOSTNAME") or _env("HOSTNAME") or "dns-collector"
        state_path = Path(_env("RAPTOR_COLLECTOR_STATE_PATH") or "/var/lib/raptor-collector/state.json")
        extra = tuple(
            item.strip()
            for item in _env("RAPTOR_COLLECTOR_ZONE_DIRS").split(",")
            if item.strip()
        )
        interval_raw = _env("RAPTOR_COLLECTOR_INTERVAL", "300")
        try:
            interval = max(30, int(interval_raw))
        except ValueError:
            interval = 300
        return cls(
            raptor_url=_env("RAPTOR_URL") or _env("RAPTOR_API_BASE_URL"),
            token=_env("RAPTOR_COLLECTOR_TOKEN"),
            enroll_token=_env("RAPTOR_ENROLL_TOKEN"),
            hostname=hostname,
            state_path=state_path,
            bind_conf=_env("RAPTOR_BIND_CONF"),
            powerdns_conf=_env("RAPTOR_POWERDNS_CONF", "/etc/powerdns/pdns.conf"),
            axfr_server=_env("RAPTOR_AXFR_SERVER"),
            tsig_name=_env("RAPTOR_TSIG_NAME"),
            tsig_secret=_env("RAPTOR_TSIG_SECRET"),
            tsig_algorithm=_env("RAPTOR_TSIG_ALGORITHM", "hmac-sha256"),
            interval_seconds=interval,
            extra_zone_dirs=extra,
        )
