import logging
import secrets
from typing import Callable

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from raptor_mcp.server import mcp
from raptor_mcp.settings import MCPSettings, load_settings

logger = logging.getLogger(__name__)


class MCPAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Starlette, expected_token: str):
        super().__init__(app)
        self._expected_token = expected_token

    def _is_authorized(self, request: Request) -> bool:
        auth_header = str(request.headers.get("Authorization") or "").strip()
        if not auth_header.lower().startswith("bearer "):
            return False
        provided_token = auth_header[7:].strip()
        if not provided_token:
            return False
        return secrets.compare_digest(provided_token, self._expected_token)

    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path.startswith("/mcp"):
            if not self._is_authorized(request):
                return JSONResponse({"error": "Unauthorized access"}, status_code=401)
        return await call_next(request)


async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"}, status_code=200)


def create_app(settings: MCPSettings | None = None) -> Starlette:
    cfg = settings or load_settings()
    mcp_asgi_app = mcp.streamable_http_app()

    app = Starlette(
        routes=[
            Route("/healthz", endpoint=healthz, methods=["GET"]),
            Mount("/", app=mcp_asgi_app),
        ]
    )
    app.add_middleware(MCPAuthMiddleware, expected_token=cfg.mcp_server_token)
    return app


__all__ = ["MCPAuthMiddleware", "create_app"]
