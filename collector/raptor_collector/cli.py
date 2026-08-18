import argparse
import json
import logging
import sys
from typing import Optional, Sequence

from raptor_collector.config import CollectorConfig
from raptor_collector.discover import discover_all
from raptor_collector.run import enroll, run_loop, run_once, zones_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="raptor-collector", description="RAPTOR DNS collector agent")
    sub = parser.add_subparsers(dest="command", required=True)

    enroll_parser = sub.add_parser("enroll", help="Exchange a bootstrap token for a rotating collector token")
    enroll_parser.add_argument("--url", dest="url")
    enroll_parser.add_argument("--token", dest="token")
    enroll_parser.add_argument("--hostname", dest="hostname")

    run_parser = sub.add_parser("run", help="Discover zones and POST RR batches to RAPTOR")
    run_parser.add_argument("--once", action="store_true", help="Collect and ship one batch, then exit")

    sub.add_parser("discover", help="Print detected BIND/PowerDNS/Windows zones without shipping")
    return parser


def _apply_overrides(config: CollectorConfig, args: argparse.Namespace) -> CollectorConfig:
    if getattr(args, "url", None):
        config.raptor_url = args.url
    if getattr(args, "hostname", None):
        config.hostname = args.hostname
    return config


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    config = _apply_overrides(CollectorConfig.from_env(), args)

    if args.command == "enroll":
        state = enroll(config, enroll_token=getattr(args, "token", None))
        print(json.dumps({"source_id": state.get("source_id"), "agent_id": state.get("agent_id")}, indent=2))
        return 0
    if args.command == "discover":
        zones = discover_all(
            bind_conf=config.bind_conf,
            powerdns_conf=config.powerdns_conf,
            extra_zone_dirs=config.extra_zone_dirs,
        )
        print(json.dumps(zones_payload(zones), indent=2))
        return 0
    if args.command == "run":
        if args.once:
            result = run_once(config)
            print(json.dumps({"zones": result.get("zones"), "ingest": result.get("ingest")}, indent=2, default=str))
            return 0
        run_loop(config)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
