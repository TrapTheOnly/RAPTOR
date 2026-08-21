"""Starlette service for RAPTOR local GGUF install/runtime."""

import asyncio
import json
import logging
import secrets
from typing import Callable

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from local_llm.manager import manager
from local_llm.settings import INTERNAL_TOKEN

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, expected_token: str):
        super().__init__(app)
        self._token = expected_token

    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path == "/healthz":
            return await call_next(request)
        provided = str(request.headers.get("X-Scanner-Token") or "").strip()
        if not provided or not self._token or not secrets.compare_digest(provided, self._token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


def create_app() -> Starlette:
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def status(_: Request) -> JSONResponse:
        return JSONResponse(manager.status())

    async def install(_: Request) -> JSONResponse:
        return JSONResponse(await manager.install(), status_code=202)

    async def cancel(_: Request) -> JSONResponse:
        return JSONResponse(await manager.cancel())

    async def pause(_: Request) -> JSONResponse:
        return JSONResponse(await manager.pause())

    async def resume(_: Request) -> JSONResponse:
        return JSONResponse(await manager.resume(), status_code=202)

    async def start(_: Request) -> JSONResponse:
        payload = await manager.start()
        code = 200 if payload.get("state") in {"ready", "starting"} else 409
        return JSONResponse(payload, status_code=code)

    async def stop(_: Request) -> JSONResponse:
        return JSONResponse(await manager.stop())

    async def uninstall(_: Request) -> JSONResponse:
        return JSONResponse(await manager.uninstall())

    async def events(_: Request) -> StreamingResponse:
        async def gen():
            last = ""
            while True:
                snapshot = json.dumps(manager.status())
                if snapshot != last:
                    yield f"data: {snapshot}\n\n"
                    last = snapshot
                await asyncio.sleep(0.6)

        return StreamingResponse(gen(), media_type="text/event-stream")

    app = Starlette(
        routes=[
            Route("/healthz", endpoint=healthz, methods=["GET"]),
            Route("/status", endpoint=status, methods=["GET"]),
            Route("/install", endpoint=install, methods=["POST"]),
            Route("/cancel", endpoint=cancel, methods=["POST"]),
            Route("/pause", endpoint=pause, methods=["POST"]),
            Route("/resume", endpoint=resume, methods=["POST"]),
            Route("/start", endpoint=start, methods=["POST"]),
            Route("/stop", endpoint=stop, methods=["POST"]),
            Route("/uninstall", endpoint=uninstall, methods=["POST"]),
            Route("/events", endpoint=events, methods=["GET"]),
        ]
    )
    app.add_middleware(AuthMiddleware, expected_token=INTERNAL_TOKEN)
    return app
