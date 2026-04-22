"""Fire-and-forget scan event reporter — delegates to RAPTOR MCP log_scan_event tool."""

import logging
from typing import Any, Dict

from mcp import ClientSession

from scanner.mcp_client import call_tool

logger = logging.getLogger(__name__)


class ScanEventReporter:
    def __init__(self, record_id: int, raptor_mcp: ClientSession):
        self._record_id = record_id
        self._mcp = raptor_mcp

    async def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        try:
            await call_tool(
                self._mcp,
                "log_scan_event",
                {"record_id": self._record_id, "event_type": event_type, "payload": payload},
            )
        except Exception as exc:
            logger.debug(f"[record {self._record_id}] log_scan_event failed ({event_type}): {exc}")


__all__ = ["ScanEventReporter"]
