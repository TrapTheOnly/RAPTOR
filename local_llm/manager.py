"""Download, verify, and run llama-server for the bundled GGUF."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from local_llm.settings import (
    ALIAS,
    CTX_SIZE,
    INFER_HOST,
    INFER_PORT,
    LLAMA_SERVER_BIN,
    MODELS_DIR,
    STATUS_PATH,
    load_definition,
    model_path,
)

logger = logging.getLogger(__name__)

STATES = (
    "not_installed",
    "downloading",
    "paused",
    "verifying",
    "starting",
    "ready",
    "stopped",
    "error",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cpu_count() -> int:
    return max(1, int(os.cpu_count() or 2))


def _gpu_available() -> bool:
    return os.path.exists("/dev/nvidia0")


def _ram_total_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 1)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def _disk_free_bytes() -> int:
    usage = shutil.disk_usage(str(MODELS_DIR))
    return int(usage.free)


class LocalModelManager:
    def __init__(self):
        self.definition = load_definition()
        self.path = model_path(self.definition)
        self.partial_path = Path(str(self.path) + ".partial")
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._cancel = asyncio.Event()
        self._pause = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._status = self._load_status()

    def _load_status(self) -> dict[str, Any]:
        if STATUS_PATH.exists():
            try:
                loaded = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    return loaded
            except json.JSONDecodeError:
                pass
        state = "stopped" if self.path.exists() else "not_installed"
        return self._base_status(state)

    def _base_status(self, state: str, **extra: Any) -> dict[str, Any]:
        size = int(self.definition.get("size_bytes") or 0)
        bytes_done = self.path.stat().st_size if self.path.exists() else (
            self.partial_path.stat().st_size if self.partial_path.exists() else 0
        )
        status = {
            "state": state,
            "ready": state == "ready",
            "bytes_done": bytes_done,
            "bytes_total": size,
            "speed_bps": 0,
            "eta_seconds": None,
            "error": "",
            "paused": state == "paused",
            "gpu": _gpu_available(),
            "ram_total_gb": _ram_total_gb(),
            "cpu_threads": _cpu_count(),
            "disk_free_bytes": _disk_free_bytes(),
            "model_path": str(self.path) if self.path.exists() else "",
            "filename": self.definition.get("filename"),
            "display_name": self.definition.get("display_name"),
            "repo_id": self.definition.get("repo_id"),
            "quant": self.definition.get("quant"),
            "license": self.definition.get("license"),
            "sha256": self.definition.get("sha256"),
            "context_length": int(self.definition.get("context_length") or CTX_SIZE),
            "recommended_ram_gb": self.definition.get("recommended_ram_gb"),
            "recommended_vram_gb": self.definition.get("recommended_vram_gb"),
            "updated_at": _utc_now(),
        }
        status.update(extra)
        return status

    def _write_status(self, **fields: Any) -> dict[str, Any]:
        current = dict(self._status)
        current.update(fields)
        current["updated_at"] = _utc_now()
        current["ready"] = current.get("state") == "ready"
        current["paused"] = current.get("state") == "paused"
        current["disk_free_bytes"] = _disk_free_bytes()
        current["gpu"] = _gpu_available()
        self._status = current
        STATUS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current

    def status(self) -> dict[str, Any]:
        snapshot = dict(self._status)
        snapshot["gpu"] = _gpu_available()
        snapshot["ram_total_gb"] = _ram_total_gb()
        snapshot["disk_free_bytes"] = _disk_free_bytes()
        snapshot["cpu_threads"] = _cpu_count()
        if self.path.exists() and snapshot.get("state") in {"not_installed", ""}:
            snapshot["state"] = "stopped"
            snapshot["bytes_done"] = self.path.stat().st_size
        return snapshot

    async def install(self) -> dict[str, Any]:
        async with self._lock:
            if self._status.get("state") in {"downloading", "verifying", "starting", "ready"}:
                return self.status()
            self._cancel.clear()
            self._pause.clear()
            self._task = asyncio.create_task(self._install_loop())
            return self._write_status(state="downloading", error="")

    async def cancel(self) -> dict[str, Any]:
        self._cancel.set()
        if self._task:
            self._task.cancel()
        return self._write_status(state="paused" if self.partial_path.exists() else "not_installed", error="Cancelled.")

    async def pause(self) -> dict[str, Any]:
        self._pause.set()
        return self._write_status(state="paused", error="")

    async def resume(self) -> dict[str, Any]:
        self._pause.clear()
        self._cancel.clear()
        if self._status.get("state") in {"paused", "not_installed", "error"}:
            self._task = asyncio.create_task(self._install_loop())
            return self._write_status(state="downloading", error="")
        return self.status()

    async def start(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._write_status(state="not_installed", error="Model file is not installed.")
        if self._proc and self._proc.returncode is None:
            return self.status()
        return await self._start_server()

    async def stop(self) -> dict[str, Any]:
        await self._stop_server()
        state = "stopped" if self.path.exists() else "not_installed"
        return self._write_status(state=state, error="")

    async def uninstall(self) -> dict[str, Any]:
        await self._stop_server()
        self._cancel.set()
        for path in (self.path, self.partial_path):
            if path.exists():
                path.unlink()
        return self._write_status(state="not_installed", bytes_done=0, error="", model_path="")

    async def _install_loop(self) -> None:
        try:
            await self._download()
            if self._cancel.is_set():
                return
            self._write_status(state="verifying", speed_bps=0)
            self._verify()
            await self._start_server()
        except asyncio.CancelledError:
            self._write_status(state="paused", error="Cancelled.")
        except Exception as exc:
            logger.exception("Local model install failed")
            self._write_status(state="error", error=str(exc)[:400])

    async def _download(self) -> None:
        url = str(self.definition.get("download_url") or "")
        total = int(self.definition.get("size_bytes") or 0)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        existing = self.partial_path.stat().st_size if self.partial_path.exists() else 0
        headers = {"User-Agent": "raptor-local-llm"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        self._write_status(state="downloading", bytes_done=existing, bytes_total=total, error="")
        started = time.monotonic()
        downloaded = existing
        last_tick = started
        last_bytes = existing
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code in {200, 206}:
                    pass
                else:
                    raise RuntimeError(f"Download failed ({response.status_code})")
                mode = "ab" if existing and response.status_code == 206 else "wb"
                if mode == "wb":
                    downloaded = 0
                with self.partial_path.open(mode) as handle:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        if self._cancel.is_set():
                            return
                        while self._pause.is_set():
                            self._write_status(state="paused", bytes_done=downloaded, speed_bps=0)
                            await asyncio.sleep(0.4)
                            if self._cancel.is_set():
                                return
                        handle.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if now - last_tick >= 0.5:
                            delta = downloaded - last_bytes
                            speed = int(delta / max(now - last_tick, 0.001))
                            remaining = max(total - downloaded, 0)
                            eta = int(remaining / speed) if speed else None
                            self._write_status(
                                state="downloading",
                                bytes_done=downloaded,
                                bytes_total=total,
                                speed_bps=speed,
                                eta_seconds=eta,
                            )
                            last_tick = now
                            last_bytes = downloaded
        if total and downloaded < total * 0.98:
            raise RuntimeError(f"Download incomplete ({downloaded} of {total} bytes).")
        self.partial_path.replace(self.path)
        self._write_status(state="verifying", bytes_done=self.path.stat().st_size, speed_bps=0)

    def _verify(self) -> None:
        expected = str(self.definition.get("sha256") or "").strip().lower()
        if not expected:
            return
        digest = hashlib.sha256()
        with self.path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            self.path.unlink(missing_ok=True)
            raise RuntimeError("Checksum mismatch. The download was discarded.")

    async def _start_server(self) -> dict[str, Any]:
        await self._stop_server()
        self._write_status(state="starting", error="")
        ngl = "99" if _gpu_available() else "0"
        cmd = [
            LLAMA_SERVER_BIN,
            "--model",
            str(self.path),
            "--alias",
            ALIAS,
            "--host",
            INFER_HOST,
            "--port",
            str(INFER_PORT),
            "--ctx-size",
            str(int(self.definition.get("context_length") or CTX_SIZE)),
            "--parallel",
            "1",
            "--jinja",
            "-ngl",
            ngl,
            "--threads",
            str(_cpu_count()),
        ]
        logger.info("Starting llama-server: %s", " ".join(cmd))
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        ready = await self._wait_ready()
        if not ready:
            await self._stop_server()
            return self._write_status(state="error", error="llama-server failed to become ready.")
        return self._write_status(
            state="ready",
            error="",
            model_path=str(self.path),
            bytes_done=self.path.stat().st_size,
        )

    async def _wait_ready(self, timeout: float = 90.0) -> bool:
        deadline = time.monotonic() + timeout
        url = f"http://127.0.0.1:{INFER_PORT}/health"
        async with httpx.AsyncClient(timeout=2.0) as client:
            while time.monotonic() < deadline:
                if self._proc and self._proc.returncode is not None:
                    return False
                try:
                    response = await client.get(url)
                    if response.status_code < 500:
                        return True
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(1.0)
        return False

    async def _stop_server(self) -> None:
        proc = self._proc
        self._proc = None
        if not proc or proc.returncode is not None:
            return
        proc.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except Exception:
            proc.kill()
            await proc.wait()


manager = LocalModelManager()
