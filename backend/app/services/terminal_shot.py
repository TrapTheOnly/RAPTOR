"""Turn Kali command transcripts into freeze PNG evidence screenshots."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).with_name("freeze.json")
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MAX_LINES = 28
MAX_LINE_LEN = 88
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

JWT_TOOL_COMMANDS = {
    "decode": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np",
    "none_alg": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np -X a",
    "key_confusion": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np -X k",
    "weak_secret": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np -C -d /opt/jwt_tool/jwt-secrets.txt",
    "claim_tamper": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np -I -pc role -pv admin",
}

STEP_ALTS = {
    "decode": "jwt_tool decode (offline, no probe)",
    "none_alg": "jwt_tool none-algorithm exploit",
    "key_confusion": "jwt_tool RSA key confusion",
    "weak_secret": "jwt_tool HMAC dictionary crack",
    "claim_tamper": "jwt_tool claim tamper",
}


def command_for_step(step: Dict[str, Any] | str) -> str:
    if isinstance(step, dict):
        explicit = str(step.get("command") or "").strip()
        name = str(step.get("step") or "")
        if explicit:
            return explicit
    else:
        name = str(step or "")
    return JWT_TOOL_COMMANDS.get(name, "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np")


def trim_output(text: str, max_lines: int = MAX_LINES) -> str:
    lines: List[str] = []
    for raw in str(text or "").splitlines():
        line = raw.rstrip()
        if len(line) > MAX_LINE_LEN:
            line = line[: MAX_LINE_LEN - 3] + "..."
        lines.append(line)
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    interesting = any("CORRECT key" in line or "Decoded Token Values" in line for line in lines)
    if interesting:
        return "\n".join(["…"] + lines[-(max_lines - 1) :])
    return "\n".join(lines[:max_lines] + ["…"])


def markdown_excerpt(text: str, max_lines: int = 16) -> str:
    """Drop jwt_tool ASCII banner so the markdown fence stays readable."""
    lines = str(text or "").splitlines()
    start = 0
    for index, line in enumerate(lines):
        if any(
            marker in line
            for marker in ("Original JWT", "Decoded Token Values", "CORRECT key", "Exploit:")
        ):
            start = index
            break
    return trim_output("\n".join(lines[start:]), max_lines=max_lines)


def transcript_for(step: Dict[str, Any]) -> str:
    command = command_for_step(step)
    body = trim_output(str(step.get("stdout") or ""))
    stderr = trim_output(str(step.get("stderr") or ""), max_lines=8)
    parts = [f"$ {command}", ""]
    if body:
        parts.append(body)
    if stderr and "CORRECT key" not in body:
        parts.extend(["", stderr])
    return "\n".join(parts).rstrip() + "\n"


def evidence_steps(suite: Iterable[Any], hits: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
    rows = [item for item in (suite or []) if isinstance(item, dict)]
    by_name = {}
    for item in rows:
        name = str(item.get("step") or "")
        if name and name not in by_name:
            by_name[name] = item
    wanted: List[Dict[str, Any]] = []
    hit_steps = {
        str(item.get("step") or "")
        for item in (hits or [])
        if isinstance(item, dict) and item.get("step")
    }
    for name in ("decode", "weak_secret"):
        row = by_name.get(name)
        if row and str(row.get("stdout") or "").strip():
            wanted.append(row)
    for name in hit_steps:
        row = by_name.get(name)
        if row and row not in wanted and str(row.get("stdout") or "").strip():
            wanted.append(row)
    return wanted[:3]


def freeze_bin() -> str:
    return str(os.getenv("FREEZE_BIN") or shutil.which("freeze") or "").strip()


def render_terminal_png(text: str) -> Optional[bytes]:
    """Run freeze with RAPTOR's config. Returns PNG bytes, or None if freeze is missing."""
    blob = str(text or "").strip("\n")
    if not blob:
        return None
    binary = freeze_bin()
    if not binary:
        logger.info("freeze is not on PATH; evidence screenshots skipped.")
        return None
    font = str(os.getenv("FREEZE_FONT") or DEFAULT_FONT)
    with tempfile.TemporaryDirectory(prefix="raptor-shot-") as tmp:
        src = Path(tmp) / "session.sh"
        out = Path(tmp) / "evidence.png"
        src.write_text(blob + "\n", encoding="utf-8")
        command = [
            binary,
            str(src),
            "-c",
            "full",
            "--margin",
            "0",
            "--theme",
            "nord",
            "-o",
            str(out),
        ]
        if Path(font).is_file():
            command.extend(["--font.file", font])
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                timeout=25,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.info("freeze skipped: %s", exc)
            return None
        if proc.returncode != 0 or not out.is_file():
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", "replace")[-400:]
            logger.info("freeze failed: %s", err or f"exit {proc.returncode}")
            return None
        png = out.read_bytes()
        if not png.startswith(PNG_MAGIC):
            logger.info("freeze wrote a non-PNG file.")
            return None
        return png


def attach_jwt_screenshots(
    suite: Iterable[Any],
    hits: Optional[Iterable[Any]] = None,
) -> List[Dict[str, str]]:
    """Persist freeze PNGs to pentest image storage. FTP lives on the app, not the worker."""
    from app.integrations.storage.offsec_storage import save_image

    shots: List[Dict[str, str]] = []
    for step in evidence_steps(suite, hits):
        png = render_terminal_png(transcript_for(step))
        if not png:
            continue
        try:
            filename = save_image(png, "png")
        except Exception as exc:
            logger.info("JWT evidence screenshot not stored: %s", exc)
            continue
        name = str(step.get("step") or "jwt_tool")
        shots.append(
            {
                "step": name,
                "alt": STEP_ALTS.get(name, f"jwt_tool {name}"),
                "url": f"/pentest/images/{filename}",
            }
        )
    return shots
