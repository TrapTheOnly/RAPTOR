import logging
from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection
from app.integrations.email.client import send_email
from app.repositories.email_config_repository import get_email_config
from app.repositories.notifications_repository import create_notifications_bulk

logger = logging.getLogger(__name__)

NOTIFICATION_TYPES = {
    "collaborator_added",
    "collaborator_removed",
    "finding_added",
    "scan_completed",
    "sync_conflict",
    "zone_sync_success",
    "zone_sync_failure",
}


def _get_usernames_by_roles(
    roles: List[str],
    db_path: str = DB_PATH,
) -> List[str]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        placeholders = ", ".join(["?"] * len(roles))
        c.execute(
            f"SELECT username FROM allowed_users WHERE role IN ({placeholders}) AND is_service_account = 0",
            tuple(roles),
        )
        return [str(row["username"]) for row in c.fetchall()]


def _get_user_email(username: str, db_path: str = DB_PATH) -> Optional[str]:
    with get_db_connection(db_path) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(
            "SELECT email FROM allowed_users WHERE username = ? AND is_service_account = 0",
            (username,),
        )
        row = c.fetchone()
    if row:
        email = row.get("email")
        return email if email and "@" in str(email) else None
    return None


def _build_email_body(title: str, message: str) -> str:
    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #1976d2, #0d47a1); padding: 20px; color: white;">
                <h2 style="margin: 0; font-size: 18px;">RAPTOR Notification</h2>
            </div>
            <div style="padding: 24px;">
                <h3 style="margin: 0 0 12px 0; color: #1976d2;">{title}</h3>
                <p style="margin: 0; line-height: 1.6; color: #555;">{message}</p>
            </div>
            <div style="padding: 12px 24px; background: #f5f5f5; font-size: 12px; color: #999;">
                This is an automated notification from RAPTOR.
            </div>
        </div>
    </body>
    </html>
    """


def notify(
    notification_type: str,
    recipients: List[str],
    title: str,
    message: str,
    actor: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    send_email_flag: bool = False,
) -> None:
    if not recipients:
        return

    unique_recipients = list(dict.fromkeys(r for r in recipients if r))
    if not unique_recipients:
        return

    try:
        notifications = [
            {
                "recipient": r,
                "type": notification_type,
                "title": title,
                "message": message,
                "actor": actor,
                "metadata": metadata,
            }
            for r in unique_recipients
        ]
        create_notifications_bulk(notifications)
    except Exception as e:
        logger.error(f"Failed to create in-app notifications: {e}")

    if not send_email_flag:
        return

    try:
        config = get_email_config()
        if not config or not int(config.get("enabled", 0)):
            return

        body_html = _build_email_body(title, message)
        for recipient in unique_recipients:
            email = _get_user_email(recipient)
            if email:
                send_email(email, f"RAPTOR: {title}", body_html, config)
    except Exception as e:
        logger.error(f"Failed to send email notifications: {e}")


def notify_by_roles(
    notification_type: str,
    roles: List[str],
    title: str,
    message: str,
    actor: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    send_email_flag: bool = False,
) -> None:
    try:
        recipients = _get_usernames_by_roles(roles)
    except Exception as e:
        logger.error(f"Failed to resolve users by roles {roles}: {e}")
        return

    notify(
        notification_type=notification_type,
        recipients=recipients,
        title=title,
        message=message,
        actor=actor,
        metadata=metadata,
        send_email_flag=send_email_flag,
    )
