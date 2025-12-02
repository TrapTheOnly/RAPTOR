import os
import logging
from datetime import timedelta
from flask import Flask
from flask_cors import CORS

from .config import SECRET_KEY, CORS_ORIGINS, APP_PORT, CERT_FILE, KEY_FILE
from .logging_config import configure_logging
from .bootstrap import bootstrap_application
from .routes import register_blueprints


def create_app():
    configure_logging()
    logger = logging.getLogger(__name__)

    app = Flask(__name__, static_folder="../static", static_url_path="")
    app.secret_key = SECRET_KEY
    app.permanent_session_lifetime = timedelta(hours=1)
    CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}})

    register_blueprints(app)

    debug_mode = APP_PORT == "5000"
    should_bootstrap = not debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if should_bootstrap:
        bootstrap_application()

    logger.info("Flask application created (debug=%s).", debug_mode)
    return app
