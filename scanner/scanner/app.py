"""Scanner HTTP service — receives scan jobs from RAPTOR backend."""

import asyncio
import logging
import secrets
from typing import Callable

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from scanner.settings import ServiceSettings, SettingsError, build_scan_settings

logger = logging.getLogger(__name__)


class ScannerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, expected_token: str):
        super().__init__(app)
        self._token = expected_token

    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path == "/healthz":
            return await call_next(request)
        provided = str(request.headers.get("X-Scanner-Token") or "").strip()
        if not provided or not secrets.compare_digest(provided, self._token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


def create_app(service_settings: ServiceSettings) -> Starlette:
    semaphore = asyncio.Semaphore(service_settings.max_concurrent_scans)
    running_tasks: dict[int, asyncio.Task] = {}
    cancel_events: dict[int, asyncio.Event] = {}

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def post_scan(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

        try:
            scan_settings = build_scan_settings(body, service_settings)
        except SettingsError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        if semaphore.locked():
            return JSONResponse(
                {"error": "Scanner is at capacity. Try again later."}, status_code=429
            )

        cancel_event = asyncio.Event()
        task = asyncio.create_task(_run_guarded(scan_settings, semaphore, cancel_event))
        job_id = int(scan_settings.job_id or 0)
        if job_id > 0:
            running_tasks[job_id] = task
            cancel_events[job_id] = cancel_event

            def _cleanup(_task: asyncio.Task, captured_id: int = job_id) -> None:
                running_tasks.pop(captured_id, None)
                cancel_events.pop(captured_id, None)

            task.add_done_callback(_cleanup)
        return JSONResponse(
            {
                "message": "Scan queued.",
                "record_id": scan_settings.record_id,
                "record_ids": list(scan_settings.record_ids),
                "wave_id": scan_settings.wave_id,
                "job_id": scan_settings.job_id,
            },
            status_code=202,
        )

    async def stop_scan(request: Request) -> JSONResponse:
        try:
            job_id = int(request.path_params.get("job_id") or 0)
        except (TypeError, ValueError):
            job_id = 0
        if job_id <= 0:
            return JSONResponse({"error": "job_id is required."}, status_code=400)
        task = running_tasks.get(job_id)
        event = cancel_events.get(job_id)
        if task is None or task.done():
            return JSONResponse({"error": "Scan is not running."}, status_code=404)
        if event is not None:
            event.set()
        task.cancel()
        return JSONResponse({"message": "Stop requested.", "job_id": job_id})

    app = Starlette(
        routes=[
            Route("/healthz", endpoint=healthz, methods=["GET"]),
            Route("/scans", endpoint=post_scan, methods=["POST"]),
            Route("/scans/{job_id:int}/stop", endpoint=stop_scan, methods=["POST"]),
        ]
    )
    app.add_middleware(ScannerAuthMiddleware, expected_token=service_settings.scanner_internal_token)
    return app


async def _run_guarded(scan_settings, semaphore: asyncio.Semaphore, cancel_event=None) -> None:
    from scanner.run import run_scan
    async with semaphore:
        record_id = scan_settings.record_id
        logger.info(f"[record {record_id}] Scan started")
        try:
            await run_scan(scan_settings, cancel_event=cancel_event)
            logger.info(f"[record {record_id}] Scan finished")
        except asyncio.CancelledError:
            logger.info(f"[record {record_id}] Scan cancelled")
        except Exception as exc:
            logger.error(f"[record {record_id}] Unhandled scan error: {exc}", exc_info=True)


__all__ = ["create_app"]
