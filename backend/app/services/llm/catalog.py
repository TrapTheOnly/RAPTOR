"""List models and live-test LLM connections."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple

import httpx

from app.services.llm.rates import apply_documented_rates
from app.services.llm.recipes import (
    PROTOCOL_ANTHROPIC,
    recipe_for,
    resolve_base_url,
)

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT = 20.0


class CatalogError(RuntimeError):
    pass


def _headers_for(provider_type: str, config: Mapping[str, Any], base_url: str) -> Dict[str, str]:
    kind = str(provider_type or "").strip().lower()
    recipe = recipe_for(kind) or {}
    auth = str(recipe.get("auth") or "")
    api_key = str(config.get("api_key") or "").strip()
    headers = {"Accept": "application/json"}
    extra = config.get("extra_headers")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if key and value not in (None, ""):
                headers[str(key)] = str(value)
    if auth == "x-api-key" and api_key:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = ANTHROPIC_VERSION
    elif auth == "bearer" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth == "azure" and api_key:
        headers["api-key"] = api_key
    project = str(config.get("project_ocid") or "").strip()
    if kind == "oracle" and project:
        headers["OpenAI-Project"] = project
    return headers


def _normalize_model(item: Any) -> Optional[Dict[str, Any]]:
    if isinstance(item, str) and item.strip():
        return {"id": item.strip(), "display_name": item.strip(), "source": "catalog", "tools": True}
    if not isinstance(item, dict):
        return None
    model_id = str(item.get("id") or item.get("model") or item.get("modelId") or "").strip()
    if not model_id:
        return None
    name = str(item.get("display_name") or item.get("name") or item.get("displayName") or model_id)
    return {
        "id": model_id,
        "display_name": name,
        "source": "catalog",
        "tools": True,
        "thinking": False,
    }


def _extract_model_list(payload: Any) -> List[Dict[str, Any]]:
    rows: List[Any] = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("data", "models", "value", "modelSummaries"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    out = []
    seen = set()
    for item in rows:
        normalized = _normalize_model(item)
        if not normalized or normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        out.append(normalized)
    return out


def merge_models(
    existing: Optional[List[Dict[str, Any]]],
    fetched: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    previous = {str(item.get("id")): dict(item) for item in existing or [] if item.get("id")}
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in fetched:
        model_id = str(item.get("id") or "")
        if not model_id or model_id in seen:
            continue
        prev = previous.get(model_id, {})
        merged = dict(item)
        merged["selected"] = bool(prev.get("selected"))
        if prev.get("display_name") and not item.get("display_name"):
            merged["display_name"] = prev["display_name"]
        for field in ("input_cost_per_1m", "output_cost_per_1m", "tools", "thinking"):
            if field in prev and field not in item:
                merged[field] = prev[field]
        merged = apply_documented_rates(merged)
        if "tools" not in merged:
            merged["tools"] = True
        out.append(merged)
        seen.add(model_id)
    for model_id, prev in previous.items():
        if model_id in seen:
            continue
        kept = apply_documented_rates(dict(prev))
        if kept.get("source") != "bundled":
            kept["source"] = kept.get("source") or "manual"
        out.append(kept)
    return out


def apply_model_updates(
    existing: Optional[List[Dict[str, Any]]],
    incoming: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if incoming is None:
        return list(existing or [])
    by_id = {str(item.get("id")): dict(item) for item in existing or [] if item.get("id")}
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in incoming:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or model_id in seen:
            continue
        prev = by_id.get(model_id, {})
        merged = dict(prev)
        merged.update({k: v for k, v in item.items() if k != "id" or v})
        merged["id"] = model_id
        merged["display_name"] = str(merged.get("display_name") or model_id)
        merged["source"] = merged.get("source") or prev.get("source") or "manual"
        if "selected" in item:
            merged["selected"] = bool(item.get("selected"))
        elif "selected" not in merged:
            merged["selected"] = True
        if "tools" not in merged:
            merged["tools"] = True
        out.append(merged)
        seen.add(model_id)
    return out


def _azure_list_url(config: Mapping[str, Any]) -> str:
    endpoint = str(config.get("endpoint") or config.get("base_url") or "").rstrip("/")
    version = str(config.get("api_version") or "2024-10-21").strip() or "2024-10-21"
    return f"{endpoint}/openai/deployments?api-version={version}"


def list_models(provider_type: str, config: Mapping[str, Any]) -> List[Dict[str, Any]]:
    kind = str(provider_type or "").strip().lower()
    recipe = recipe_for(kind)
    if not recipe:
        raise CatalogError(f"Unknown provider type: {provider_type}")
    if kind == "local":
        from app.services.llm.recipes import default_local_models

        return default_local_models()
    if kind == "bedrock":
        return _list_bedrock(config)
    base_url = resolve_base_url(kind, config)
    if not base_url:
        raise CatalogError("Base URL is required to list models.")
    if kind == "azure":
        url = _azure_list_url(config)
    else:
        path = str(recipe.get("list_path") or "/models")
        url = f"{base_url}{path if path.startswith('/') else '/' + path}"
    headers = _headers_for(kind, config, base_url)
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise CatalogError(f"Failed to list models: {exc}") from exc
    if response.status_code >= 400:
        raise CatalogError(f"List models failed ({response.status_code}): {response.text[:240]}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise CatalogError("List models returned non-JSON.") from exc
    models = _extract_model_list(payload)
    if kind == "bedrock":
        models = [item for item in models if "anthropic" in item["id"].lower()]
    return models


def _list_bedrock(config: Mapping[str, Any]) -> List[Dict[str, Any]]:
    region = str(config.get("aws_region") or "us-east-1").strip() or "us-east-1"
    access_key = str(config.get("access_key_id") or "").strip()
    secret = str(config.get("aws_secret_access_key") or "").strip()
    if not access_key or not secret:
        return []
    try:
        import boto3

        kwargs: Dict[str, Any] = {"region_name": region}
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret
        session_token = str(config.get("aws_session_token") or "").strip()
        if session_token:
            kwargs["aws_session_token"] = session_token
        client = boto3.client("bedrock", **kwargs)
        response = client.list_foundation_models(byOutputModality="TEXT")
    except Exception as exc:
        raise CatalogError(f"Bedrock list models failed: {exc}") from exc
    summaries = response.get("modelSummaries") or []
    out = []
    for item in summaries:
        model_id = str(item.get("modelId") or "")
        if "anthropic" not in model_id.lower():
            continue
        out.append(
            {
                "id": model_id,
                "display_name": str(item.get("modelName") or model_id),
                "source": "catalog",
                "tools": True,
                "thinking": True,
            }
        )
    return out


def _pick_test_model(config: Mapping[str, Any], models: Optional[List[Dict[str, Any]]]) -> str:
    selected = [
        str(item.get("id") or "")
        for item in models or []
        if item.get("selected") and item.get("id")
    ]
    if selected:
        return selected[0]
    if models:
        return str(models[0].get("id") or "")
    return str(config.get("test_model_id") or "").strip()


def probe_connection(
    provider_type: str,
    config: Mapping[str, Any],
    models: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str]:
    kind = str(provider_type or "").strip().lower()
    recipe = recipe_for(kind)
    if not recipe:
        return False, f"Unknown provider type: {provider_type}"
    if kind == "local":
        return True, "Local runtime is managed on the Local model tab."
    model_id = _pick_test_model(config, models)
    try:
        if kind == "bedrock":
            return _test_bedrock(config, model_id)
        protocol = str(recipe.get("protocol") or "")
        if protocol == PROTOCOL_ANTHROPIC:
            if not model_id:
                listed = list_models(kind, config)
                return True, f"Reached {kind}. {len(listed)} models listed."
            _test_anthropic(kind, config, model_id)
            return True, f"Reachable. Tested {model_id}."
        listed = []
        if recipe.get("catalog"):
            try:
                listed = list_models(kind, config)
            except CatalogError:
                listed = []
        if not model_id and listed:
            model_id = listed[0]["id"]
        if not model_id:
            if listed:
                return True, f"Reached {kind}. {len(listed)} models listed."
            raise CatalogError("No model id available to test.")
        _test_openai(kind, config, model_id)
        return True, f"Reachable. Tested {model_id}."
    except CatalogError as exc:
        return False, str(exc)
    except Exception as exc:
        logger.exception("LLM connection test failed")
        return False, str(exc)


def _test_anthropic(provider_type: str, config: Mapping[str, Any], model_id: str) -> None:
    base_url = resolve_base_url(provider_type, config)
    url = f"{base_url}/v1/messages"
    headers = _headers_for(provider_type, config, base_url)
    headers["Content-Type"] = "application/json"
    body = {
        "model": model_id,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise CatalogError(f"Test request failed: {exc}") from exc
    if response.status_code >= 400:
        raise CatalogError(f"Test failed ({response.status_code}): {response.text[:240]}")


def _azure_chat_url(config: Mapping[str, Any], model_id: str) -> str:
    endpoint = str(config.get("endpoint") or config.get("base_url") or "").rstrip("/")
    version = str(config.get("api_version") or "2024-10-21").strip() or "2024-10-21"
    return f"{endpoint}/openai/deployments/{model_id}/chat/completions?api-version={version}"


def _test_openai(provider_type: str, config: Mapping[str, Any], model_id: str) -> None:
    kind = str(provider_type or "").strip().lower()
    if kind == "azure":
        url = _azure_chat_url(config, model_id)
    else:
        base_url = resolve_base_url(kind, config)
        url = f"{base_url}/chat/completions"
    headers = _headers_for(kind, config, resolve_base_url(kind, config))
    headers["Content-Type"] = "application/json"
    body = {
        "model": model_id,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise CatalogError(f"Test request failed: {exc}") from exc
    if response.status_code >= 400:
        raise CatalogError(f"Test failed ({response.status_code}): {response.text[:240]}")


def _test_bedrock(config: Mapping[str, Any], model_id: str) -> Tuple[bool, str]:
    region = str(config.get("aws_region") or "us-east-1").strip() or "us-east-1"
    bearer = str(config.get("aws_bearer_token") or "").strip()
    access_key = str(config.get("access_key_id") or "").strip()
    secret = str(config.get("aws_secret_access_key") or "").strip()
    if not bearer and not (access_key and secret):
        import os

        bearer = str(os.getenv("AWS_BEARER_TOKEN_BEDROCK") or "").strip()
    if not model_id:
        if access_key and secret:
            listed = _list_bedrock(config)
            return True, f"Bedrock credentials accepted. {len(listed)} Anthropic models listed."
        if bearer:
            return True, "Bearer token present. Add a model ID to run a live completion test."
        return False, "Bedrock needs a bearer token or access key + secret."
    if bearer:
        url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {bearer}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise CatalogError(f"Bedrock test failed: {exc}") from exc
        if response.status_code >= 400:
            raise CatalogError(f"Bedrock test failed ({response.status_code}): {response.text[:240]}")
        return True, f"Reachable. Tested {model_id}."
    try:
        import boto3

        kwargs: Dict[str, Any] = {"region_name": region}
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret
        session_token = str(config.get("aws_session_token") or "").strip()
        if session_token:
            kwargs["aws_session_token"] = session_token
        client = boto3.client("bedrock-runtime", **kwargs)
        client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=b'{"anthropic_version":"bedrock-2023-05-31","max_tokens":1,"messages":[{"role":"user","content":"ping"}]}',
        )
    except Exception as exc:
        raise CatalogError(f"Bedrock test failed: {exc}") from exc
    return True, f"Reachable. Tested {model_id}."


__all__ = [
    "CatalogError",
    "apply_model_updates",
    "list_models",
    "merge_models",
    "probe_connection",
]
