import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import httpx

from app.repositories.scanner_config_repository import (
    count_running_scans,
    get_scanner_config,
    update_scanner_config,
)
from app.repositories.service_api_repository import fetch_pentest_row

logger = logging.getLogger(__name__)

SCANNER_BASE_URL = os.getenv("SCANNER_BASE_URL", "http://scanner:8082")
SCANNER_INTERNAL_TOKEN = os.getenv("SCANNER_INTERNAL_TOKEN", "")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_scanner_config_payload() -> Tuple[Dict[str, Any], int]:
    try:
        cfg = get_scanner_config()
        if not cfg:
            return {"error": "Scanner config not found."}, 404
        return {"config": cfg}, 200
    except Exception as exc:
        logger.error(f"Failed to fetch scanner config: {exc}")
        return {"error": "Failed to fetch scanner config."}, 500


def update_scanner_config_payload(
    fields: Dict[str, Any], actor: str
) -> Tuple[Dict[str, Any], int]:
    allowed = {
        "aws_region", "bedrock_model_id", "cost_limit_usd",
        "input_cost_per_1m", "output_cost_per_1m",
        "max_concurrent_scans", "enabled",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return {"error": "No valid fields to update."}, 400

    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    if "max_concurrent_scans" in updates:
        try:
            val = int(updates["max_concurrent_scans"])
            if val < 1 or val > 10:
                return {"error": "max_concurrent_scans must be between 1 and 10."}, 400
            updates["max_concurrent_scans"] = val
        except (TypeError, ValueError):
            return {"error": "max_concurrent_scans must be an integer."}, 400
    for cost_field in ("cost_limit_usd", "input_cost_per_1m", "output_cost_per_1m"):
        if cost_field not in updates:
            continue
        try:
            val = float(updates[cost_field])
            if val <= 0:
                return {"error": f"{cost_field} must be greater than 0."}, 400
            updates[cost_field] = val
        except (TypeError, ValueError):
            return {"error": f"{cost_field} must be a number."}, 400

    updates["updated_by"] = actor
    updates["updated_at"] = _utc_now_iso()

    try:
        update_scanner_config(updates)
        cfg = get_scanner_config()
        return {"message": "Scanner config updated.", "config": cfg}, 200
    except Exception as exc:
        logger.error(f"Failed to update scanner config: {exc}")
        return {"error": "Failed to update scanner config."}, 500


def launch_scan_payload(record_id: int) -> Tuple[Dict[str, Any], int]:
    try:
        cfg = get_scanner_config()
    except Exception as exc:
        logger.error(f"Failed to read scanner config: {exc}")
        return {"error": "Failed to read scanner config."}, 500

    if not cfg:
        return {"error": "Scanner is not configured."}, 503
    if not int(cfg.get("enabled") or 0):
        return {"error": "Scanner is disabled. Enable it in Admin Settings."}, 503
    if not str(cfg.get("bedrock_model_id") or "").strip():
        return {"error": "Bedrock model ID is not configured."}, 503

    try:
        pentest = fetch_pentest_row(record_id)
    except Exception as exc:
        logger.error(f"Failed to fetch pentest row {record_id}: {exc}")
        return {"error": "Failed to fetch pentest record."}, 500
    if not pentest:
        return {"error": "Pentest record not found."}, 404

    if str(pentest.get("scan_status") or "idle") == "running":
        return {"error": "A scan is already running for this record."}, 409

    try:
        running = count_running_scans()
        max_concurrent = int(cfg.get("max_concurrent_scans") or 2)
        if running >= max_concurrent:
            return {
                "error": f"Maximum concurrent scans reached ({max_concurrent}). Try again later."
            }, 429
    except Exception as exc:
        logger.error(f"Failed to count running scans: {exc}")
        return {"error": "Failed to check scan capacity."}, 500

    try:
        _dispatch_scan(record_id, cfg)
    except Exception as exc:
        logger.error(f"Failed to dispatch scan for record {record_id}: {exc}")
        return {"error": "Failed to dispatch scan to scanner service."}, 502

    return {"message": "Scan launched.", "record_id": record_id}, 202


def _dispatch_scan(record_id: int, cfg: Dict[str, Any]) -> None:
    url = f"{SCANNER_BASE_URL}/scans"
    headers = {"X-Scanner-Token": SCANNER_INTERNAL_TOKEN}
    body = {
        "record_id": record_id,
        "aws_region": cfg["aws_region"],
        "bedrock_model_id": cfg["bedrock_model_id"],
        "cost_limit_usd": float(cfg.get("cost_limit_usd") or 5.0),
        "input_cost_per_1m": float(cfg.get("input_cost_per_1m") or 3.0),
        "output_cost_per_1m": float(cfg.get("output_cost_per_1m") or 15.0),
        "kali_server_url": os.getenv("KALI_SERVER_URL", "http://kali:5000"),
        "kali_client_path": os.getenv("KALI_CLIENT_PATH", "/opt/mcp-kali-server/mcp_server.py"),
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, json=body, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(f"Scanner returned {resp.status_code}: {resp.text[:200]}")


__all__ = [
    "get_scanner_config_payload",
    "launch_scan_payload",
    "update_scanner_config_payload",
]
