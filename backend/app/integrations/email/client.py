import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


def test_smtp_connection(config: Dict[str, Any]) -> Tuple[bool, str]:
    """Test SMTP connectivity and auth without sending email. Returns (success, message)."""
    if not config:
        return False, "No configuration provided."
    server = None
    try:
        smtp_host = config["smtp_host"]
        smtp_port = int(config.get("smtp_port", 587))
        use_tls = bool(int(config.get("smtp_use_tls", 1)))

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        if use_tls:
            server.starttls()

        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.quit()
        return True, "SMTP connection successful."
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed: {e}"
    except smtplib.SMTPConnectError as e:
        return False, f"Connection failed: {e}"
    except Exception as e:
        return False, str(e)
    finally:
        if server:
            try:
                server.close()
            except Exception:
                pass


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    config: Dict[str, Any],
) -> bool:
    if not to_email or not config:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{config.get('sender_name', 'RAPTOR')} <{config['sender_email']}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        smtp_host = config["smtp_host"]
        smtp_port = int(config.get("smtp_port", 587))
        use_tls = bool(int(config.get("smtp_use_tls", 1)))

        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)

        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.sendmail(config["sender_email"], to_email, msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
