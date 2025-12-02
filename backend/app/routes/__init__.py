from .auth import auth_bp
from .records import records_bp
from .admin import admin_bp
from .pentest import pentest_bp
from .status import status_bp
from .frontend import frontend_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pentest_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(frontend_bp)
