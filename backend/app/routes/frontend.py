from flask import Flask, send_from_directory

from app.http.decorators.login_required import login_required_html


def register_frontend_routes(app: Flask) -> None:
    @app.route("/")
    @login_required_html
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(404)
    def not_found(error):
        return send_from_directory(app.static_folder, "index.html")
