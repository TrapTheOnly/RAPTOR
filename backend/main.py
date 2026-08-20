import logging
import os

from dotenv import load_dotenv

from app import create_app
from app.bootstrap.db_init import init_db
from app.config import env_flag
from app.services.admin_auth_service import init_admin_db

load_dotenv()

logger = logging.getLogger(__name__)

app = create_app()


if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        init_db()
        init_admin_db()

    port = os.getenv("APP_PORT")
    use_tls = env_flag("APP_USE_TLS", False)
    logger.info(f"Starting Flask server on port {port}...")
    if use_tls:
        cert_file = os.getenv("CERT_FILE")
        key_file = os.getenv("KEY_FILE")
        if not cert_file or not key_file:
            raise RuntimeError(
                "APP_USE_TLS is enabled but CERT_FILE/KEY_FILE are not set."
            )
        app.run(host="0.0.0.0", port=port, ssl_context=(cert_file, key_file), debug=True)
    else:
        app.run(host="0.0.0.0", port=port, debug=True)
