"""Fire-and-forget scan event reporter — delegates to RAPTOR MCP log_scan_event tool."""

import logging
from typing import Any, Dict, Optional

from mcp import ClientSession

from scanner.mcp_client import call_tool

logger = logging.getLogger(__name__)


class ScanEventReporter:
    def __init__(self, record_id: int, raptor_mcp: ClientSession, job_id: int = 0):
        self._record_id = record_id
        self._job_id = int(job_id or 0)
        self._mcp = raptor_mcp

    async def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
        record_id: Optional[int] = None,
    ) -> None:
        target_id = int(record_id or self._record_id)
        arguments: Dict[str, Any] = {
            "record_id": target_id,
            "event_type": event_type,
            "payload": payload,
        }
        if self._job_id:
            arguments["job_id"] = self._job_id
        try:
            await call_tool(self._mcp, "log_scan_event", arguments)
        except Exception as exc:
            logger.debug(f"[record {target_id}] log_scan_event failed ({event_type}): {exc}")


__all__ = ["ScanEventReporter"]
