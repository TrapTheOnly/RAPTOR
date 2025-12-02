from app import create_app
from app.config import APP_PORT, CERT_FILE, KEY_FILE

app = create_app()


if __name__ == "__main__":
    debug_mode = APP_PORT == "5000"
    if debug_mode:
        app.run(host="0.0.0.0", port=APP_PORT, ssl_context=(CERT_FILE, KEY_FILE), debug=True)
    else:
        app.run(host="0.0.0.0", port=APP_PORT, debug=False)
