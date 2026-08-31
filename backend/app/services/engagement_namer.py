"""Short AI titles for wave engagements. Never send secrets (JWT bodies, passwords)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import httpx

from app.domain.burp.fields import jwt_like
from app.repositories.applications_repository import fetch_application
from app.repositories.llm_connections_repository import get_connection
from app.repositories.scanner_config_repository import get_scanner_config
from app.services.llm.catalog import _azure_chat_url, _headers_for
from app.services.llm.recipes import PROTOCOL_ANTHROPIC, PROTOCOL_OPENAI, recipe_for, resolve_base_url

logger = logging.getLogger(__name__)

TITLE_MAX = 72
NAME_TIMEOUT = 8.0

_KIND_LABELS = {
    "jwt": "JWT suite",
    "analyze": "Burp analyze",
    "ai_scan": "AI scan",
}


def fallback_title(*, kind: str, host: str = "", path: str = "", host_count: int = 0, wave_name: str = "") -> str:
    label = _KIND_LABELS.get(str(kind or "").strip(), "Engagement")
    host = str(host or "").strip()
    path = str(path or "").strip()
    wave = str(wave_name or "").strip()
    if kind == "ai_scan":
        if host_count:
            return f"{label} · {host_count} host{'s' if host_count != 1 else ''}"
        if wave:
            return f"{label} · {wave}"
        return label
    if kind == "analyze":
        if host_count:
            return f"{label} · {host_count} endpoint{'s' if host_count != 1 else ''}"
        if host:
            return f"{label} on {host}"[:TITLE_MAX]
        if wave:
            return f"{label} · {wave}"[:TITLE_MAX]
        return label
    if host and path and path not in {"", "/"}:
        return f"{label} on {host}{path}"[:TITLE_MAX]
    if host:
        return f"{label} on {host}"[:TITLE_MAX]
    return label


def sanitize_title(raw: str, fallback: str) -> str:
    text = str(raw or "").replace("\n", " ").replace("\r", " ").strip()
    text = text.strip(" \"'`")
    text = re.sub(r"\s+", " ", text)
    if not text:
        return fallback
    return text[:TITLE_MAX]


def name_engagement(
    *,
    kind: str,
    host: str = "",
    path: str = "",
    wave_name: str = "",
    app_name: str = "",
    host_count: int = 0,
    extra: str = "",
) -> str:
    fallback = fallback_title(
        kind=kind, host=host, path=path, host_count=host_count, wave_name=wave_name
    )
    prompt = (
        "Name this RAPTOR pentest engagement in 4 to 8 words. "
        "Return only the title. No quotes, no secrets, no JWT text.\n"
        f"Kind: {kind}\n"
        f"App: {app_name or 'unknown'}\n"
        f"Wave: {wave_name or 'unknown'}\n"
        f"Host: {host or 'n/a'}\n"
        f"Path: {path or 'n/a'}\n"
        f"Hosts in scope: {host_count or 'n/a'}\n"
    )
    extra_text = _notes_for_prompt(extra)
    if extra_text:
        prompt += f"Notes: {extra_text}\n"
    try:
        titled = _complete(prompt, max_tokens=24)
    except Exception as exc:
        logger.info("Engagement naming fell back (%s): %s", kind, exc)
        return fallback
    return sanitize_title(titled, fallback)


def complete_text(prompt: str, *, max_tokens: int = 120) -> str:
    return _complete(prompt, max_tokens=max_tokens)


def _notes_for_prompt(extra: str) -> str:
    text = str(extra or "").strip()
    if not text:
        return ""
    for _ in range(8):
        token = jwt_like(text)
        if not token:
            break
        text = text.replace(token, "[redacted]")
    return text[:240]


def app_and_wave_names(wave: Optional[Dict[str, Any]]) -> Dict[str, str]:
    wave = wave or {}
    app_id = wave.get("application_id")
    app = fetch_application(int(app_id)) if app_id else None
    return {
        "wave_name": str(wave.get("name") or ""),
        "app_name": str((app or {}).get("name") or ""),
    }


def _complete(prompt: str, max_tokens: int = 24) -> str:
    cfg = get_scanner_config() or {}
    connection_id = int(cfg.get("active_connection_id") or 0)
    model_id = str(cfg.get("active_model_id") or "").strip()
    if not connection_id or not model_id:
        raise RuntimeError("No active LLM connection.")
    row = get_connection(connection_id, decrypt=True, mask=False)
    if not row or not int(row.get("enabled") or 0):
        raise RuntimeError("Active LLM connection is unavailable.")
    kind = str(row.get("type") or "").strip().lower()
    config = row.get("config") if isinstance(row.get("config"), dict) else {}
    recipe = recipe_for(kind) or {}
    protocol = str(recipe.get("protocol") or PROTOCOL_OPENAI)
    if protocol == PROTOCOL_ANTHROPIC:
        return _anthropic(kind, config, model_id, prompt, max_tokens=max_tokens)
    return _openai(kind, config, model_id, prompt, max_tokens=max_tokens)


def _openai(kind: str, config: Dict[str, Any], model_id: str, prompt: str, max_tokens: int = 24) -> str:
    if kind == "azure":
        url = _azure_chat_url(config, model_id)
    else:
        url = f"{resolve_base_url(kind, config)}/chat/completions"
    headers = _headers_for(kind, config, resolve_base_url(kind, config))
    headers["Content-Type"] = "application/json"
    body = {
        "model": model_id,
        "max_tokens": max(24, int(max_tokens or 24)),
        "temperature": 0.4,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=NAME_TIMEOUT if max_tokens <= 24 else 16.0) as client:
        response = client.post(url, headers=headers, json=body)
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Empty LLM response.")
    message = (choices[0] or {}).get("message") or {}
    return str(message.get("content") or "")


def _anthropic(kind: str, config: Dict[str, Any], model_id: str, prompt: str, max_tokens: int = 24) -> str:
    base = resolve_base_url(kind, config).rstrip("/")
    url = f"{base}/v1/messages"
    headers = _headers_for(kind, config, base)
    headers["Content-Type"] = "application/json"
    body = {
        "model": model_id,
        "max_tokens": max(24, int(max_tokens or 24)),
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=NAME_TIMEOUT if max_tokens <= 24 else 16.0) as client:
        response = client.post(url, headers=headers, json=body)
    response.raise_for_status()
    payload = response.json()
    blocks = payload.get("content") if isinstance(payload, dict) else None
    if isinstance(blocks, list):
        texts = [str(item.get("text") or "") for item in blocks if isinstance(item, dict)]
        return " ".join(part for part in texts if part)
    return str(payload.get("completion") or "")
