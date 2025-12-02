"""
Compatibility shim: re-export admin helpers from app.services.admin.
"""
from app.services.admin import (  # noqa: F401
    init_admin_db,
    admin_login,
    check_current_admin_password,
    change_admin_password,
    get_existing_users,
    delete_user,
    admin_required,
)
