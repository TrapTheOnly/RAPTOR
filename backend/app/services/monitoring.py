import os
import logging
import threading
from typing import Callable
from ..config import DB_PATH
from modules.dns_monitor import DNSZoneMonitor

logger = logging.getLogger(__name__)


def run_dns_monitoring():
    """
    Run DNS zone file monitoring check using the DNSZoneMonitor class.
    """
    try:
        shared_path = os.getenv("SHARED_PATH", "")
        monitor = DNSZoneMonitor(db_path=DB_PATH, shared_path=shared_path)
        result = monitor.run_monitoring_check()
        logger.info(
            "DNS monitoring check completed: %s - %s",
            result.get("status"),
            result.get("message"),
        )
        return result
    except Exception as e:
        logger.error("Error in DNS monitoring: %s", e)
        return {
            "status": "error",
            "message": f"DNS monitoring failed: {str(e)}",
        }


def periodic_update(interval: int, update_function: Callable):
    """
    Run `update_function` every `interval` seconds in a separate thread.
    """
    def wrapper():
        update_function()
        threading.Timer(interval, wrapper).start()

    threading.Timer(interval, wrapper).start()
