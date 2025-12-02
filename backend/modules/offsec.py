"""
Compatibility shim: re-export pentest helpers from app.services.pentest.
"""
from app.services.pentest import (  # noqa: F401
    ftp_connect,
    save_report,
    delete_report,
    pentest_required,
    get_pentest_data_internal,
    get_record_details_internal,
    get_pentest_users_internal,
)

# Re-export view functions from the routes layer for backward compatibility
from app.routes.pentest import (  # noqa: F401
    get_pentest_users,
    create_or_update_pentest_data,
    delete_pentest_data,
    get_pentest_data,
    get_report,
    delete_report_route,
    get_pentest_history,
)
