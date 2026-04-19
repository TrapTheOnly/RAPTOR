import logging

import uvicorn

from raptor_mcp.app import create_app
from raptor_mcp.settings import SettingsError, load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def build_app():
    return create_app()


app = build_app()


if __name__ == "__main__":
    try:
        settings = load_settings()
    except SettingsError as exc:
        raise SystemExit(f"Invalid MCP configuration: {exc}") from exc

    uvicorn.run(
        "raptor_mcp.main:app",
        host="0.0.0.0",
        port=settings.mcp_port,
        reload=False,
        access_log=True,
    )
