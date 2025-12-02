import logging
from .db import init_db
from .services.records import update_data
from .services.monitoring import run_dns_monitoring, periodic_update
from .services.admin import init_admin_db
from .config import UPDATE_TIME_SECONDS

logger = logging.getLogger(__name__)


def bootstrap_application():
    """
    Initialise the database, seed the admin user, refresh data, and start background jobs.
    """
    init_db()
    init_admin_db()
    update_data()

    # Run initial DNS monitoring check to populate system status.
    run_dns_monitoring()

    zone_update_interval = UPDATE_TIME_SECONDS
    periodic_update(zone_update_interval, update_data)

    # Run DNS monitoring every 24 hours (86400 seconds)
    dns_monitor_interval = 86400
    periodic_update(dns_monitor_interval, run_dns_monitoring)
