import os
from datetime import timedelta


def create_app():
    from dotenv import load_dotenv
    from flask import Flask
    from flask_cors import CORS

    from app.config import BASE_DIR, configure_logging, env_flag
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.docs import docs_bp
    from app.routes.frontend import register_frontend_routes
    from app.routes.metadata import metadata_bp
    from app.routes.notifications import notifications_bp
    from app.routes.offsec_routes import register_offsec_routes
    from app.routes.records import records_bp
    from app.routes.scanner import scanner_bp
    from app.routes.service_api import service_api_bp
    from app.services.session_policy_service import SESSION_IDLE_TIMEOUT_SECONDS

    load_dotenv()
    configure_logging()

    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, "static"),
        static_url_path="",
    )

    app.secret_key = os.getenv("SECRET_KEY")
    app.permanent_session_lifetime = timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS)
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["SESSION_COOKIE_SECURE"] = env_flag(
        "SESSION_COOKIE_SECURE",
        env_flag("APP_USE_TLS"),
    )

    CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "*").split(",")}})

    app.register_blueprint(records_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(metadata_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(service_api_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(scanner_bp)
    register_offsec_routes(app)
    register_frontend_routes(app)

    return app
