import logging

import uvicorn

from scanner.app import create_app
from scanner.settings import SettingsError, load_service_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def build_app():
    settings = load_service_settings()
    return create_app(settings)


app = build_app()

if __name__ == "__main__":
    try:
        settings = load_service_settings()
    except SettingsError as exc:
        raise SystemExit(f"Invalid scanner configuration: {exc}") from exc

    uvicorn.run(
        "scanner.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=True,
    )
