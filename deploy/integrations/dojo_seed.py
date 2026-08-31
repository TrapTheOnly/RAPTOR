#!/usr/bin/env python3
"""Wait for DefectDojo, create RAPTOR lab products/engagements, mint an API token."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

DOJO_URL = os.environ.get("DOJO_URL", "http://dojo-nginx:8080").rstrip("/")
PUBLIC_URL = os.environ.get("DOJO_PUBLIC_URL", "http://localhost:8088").rstrip("/")
ADMIN_USER = os.environ.get("DOJO_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("DOJO_ADMIN_PASSWORD", "RaptoR!dojo1")
OUT_DIR = os.environ.get("SEED_OUT_DIR", "/out")
TIMEOUT = int(os.environ.get("DOJO_SEED_TIMEOUT", "600"))

PRODUCTS = [
    {
        "name": "RAPTOR Lab",
        "description": "Primary product for RAPTOR pentest exports.",
        "business_criticality": "high",
        "platform": "web",
        "lifecycle": "production",
        "origin": "internal",
        "tags": ["raptor", "pentest", "lab"],
        "engagements": ["Baseline assessment"],
    },
    {
        "name": "Legacy Intranet",
        "description": "Second product so RAPTOR can choose among product mappings.",
        "business_criticality": "medium",
        "platform": "web service",
        "lifecycle": "retirement",
        "origin": "internal",
        "tags": ["legacy", "internal"],
        "engagements": ["Decommission review"],
    },
]


def log(message: str) -> None:
    print(message, flush=True)


def wait_ready(client: httpx.Client) -> None:
    deadline = time.time() + TIMEOUT
    last = ""
    while time.time() < deadline:
        try:
            response = client.get("/login")
            if response.status_code in {200, 302}:
                api = client.get("/api/v2/")
                if api.status_code in {200, 401, 403}:
                    log(f"DefectDojo is up ({response.status_code}, api {api.status_code})")
                    return
                last = f"api HTTP {api.status_code}"
            else:
                last = f"login HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last = str(exc)
        log(f"Waiting for DefectDojo: {last}")
        time.sleep(5)
    raise SystemExit(f"DefectDojo did not become ready: {last}")


def mint_token(client: httpx.Client) -> str:
    response = client.post(
        "/api/v2/api-token-auth/",
        json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
    )
    if response.status_code >= 400:
        response = client.post(
            "/api/v2/api-token-auth/",
            data={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
        )
    body = _json(response)
    token = ""
    if isinstance(body, dict):
        token = str(body.get("token") or body.get("key") or "")
    if not token:
        raise SystemExit(f"Could not mint DefectDojo token: HTTP {response.status_code} {body}")
    log("Minted DefectDojo API token")
    return token


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": (response.text or "")[:400], "status": response.status_code}


def api(client: httpx.Client, method: str, path: str, **kwargs) -> Tuple[int, Any]:
    response = client.request(method, path, **kwargs)
    return response.status_code, _json(response)


def list_results(client: httpx.Client, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    status, body = api(client, "GET", path, params=params or {"limit": 200})
    if status >= 400:
        log(f"GET {path} -> {status} {body}")
        return []
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict):
        rows = body.get("results") or body.get("objects") or []
        return [item for item in rows if isinstance(item, dict)]
    return []


def find_named(rows: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    wanted = name.strip().lower()
    for item in rows:
        if str(item.get("name") or "").strip().lower() == wanted:
            return item
    return None


def ensure_product_type(client: httpx.Client) -> int:
    rows = list_results(client, "/api/v2/product_types/")
    existing = find_named(rows, "RAPTOR") or (rows[0] if rows else None)
    if existing and str(existing.get("name") or "").lower() == "raptor":
        return int(existing["id"])
    status, body = api(
        client,
        "POST",
        "/api/v2/product_types/",
        json={
            "name": "RAPTOR",
            "description": "Products fed by RAPTOR pentest exports.",
            "critical_product": True,
            "key_product": True,
        },
    )
    if status >= 400 or not isinstance(body, dict) or body.get("id") is None:
        if existing:
            log(f"Using existing product type {existing.get('name')}")
            return int(existing["id"])
        raise SystemExit(f"Could not create product type: {status} {body}")
    log("Created product type RAPTOR")
    return int(body["id"])


def ensure_product(client: httpx.Client, prod_type: int, spec: Dict[str, Any]) -> Dict[str, Any]:
    existing = find_named(list_results(client, "/api/v2/products/"), spec["name"])
    payload = {
        "name": spec["name"],
        "description": spec["description"],
        "prod_type": prod_type,
        "business_criticality": spec["business_criticality"],
        "platform": spec["platform"],
        "lifecycle": spec["lifecycle"],
        "origin": spec["origin"],
        "tags": spec["tags"],
    }
    if existing:
        api(client, "PATCH", f"/api/v2/products/{existing['id']}/", json=payload)
        log(f"Updated product {spec['name']}")
        return {"id": str(existing["id"]), "name": spec["name"]}
    status, body = api(client, "POST", "/api/v2/products/", json=payload)
    if status >= 400 or not isinstance(body, dict) or body.get("id") is None:
        raise SystemExit(f"Could not create product {spec['name']}: {status} {body}")
    log(f"Created product {spec['name']}")
    return {"id": str(body["id"]), "name": spec["name"]}


def ensure_engagement(client: httpx.Client, product_id: str, name: str) -> Dict[str, str]:
    rows = list_results(client, "/api/v2/engagements/", {"product": product_id, "limit": 200})
    existing = find_named(rows, name)
    if existing:
        return {"id": str(existing["id"]), "name": name}
    today = date.today()
    status, body = api(
        client,
        "POST",
        "/api/v2/engagements/",
        json={
            "name": name,
            "product": int(product_id),
            "target_start": today.isoformat(),
            "target_end": (today + timedelta(days=30)).isoformat(),
            "engagement_type": "Interactive",
            "status": "In Progress",
            "description": "Seeded for RAPTOR lab exports. Per-wave mode will create additional engagements.",
        },
    )
    if status >= 400 or not isinstance(body, dict) or body.get("id") is None:
        raise SystemExit(f"Could not create engagement {name}: {status} {body}")
    log(f"Created engagement {name}")
    return {"id": str(body["id"]), "name": name}


def write_credentials(payload: Dict[str, Any]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "defectdojo.json")
    merged_path = os.path.join(OUT_DIR, "credentials.json")
    existing: Dict[str, Any] = {}
    if os.path.exists(merged_path):
        try:
            with open(merged_path, encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing["defectdojo"] = payload
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    with open(merged_path, "w", encoding="utf-8") as handle:
        json.dump(existing, handle, indent=2)
    log(f"Wrote {merged_path}")


def main() -> int:
    log(f"Seeding DefectDojo at {DOJO_URL} (browser URL {PUBLIC_URL})")
    with httpx.Client(base_url=DOJO_URL, timeout=60.0, follow_redirects=True) as anon:
        wait_ready(anon)
        token = mint_token(anon)

    with httpx.Client(
        base_url=DOJO_URL,
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        prod_type = ensure_product_type(client)
        products = []
        engagements = []
        for spec in PRODUCTS:
            product = ensure_product(client, prod_type, spec)
            products.append(product)
            for engagement_name in spec["engagements"]:
                engagement = ensure_engagement(client, product["id"], engagement_name)
                engagements.append({**engagement, "product": product["name"]})
        payload = {
            "browser_url": PUBLIC_URL,
            "docker_url": "http://dojo:8080",
            "raptor_base_url": "http://host.docker.internal:8088",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
            "api_key": token,
            "product_type": "RAPTOR",
            "products": products,
            "engagements": engagements,
            "recommended_template": {
                "name": "RAPTOR Lab / per wave",
                "product": "RAPTOR Lab",
                "engagement_mode": "per_wave",
                "test_mode": "create",
            },
            "fields_not_in_raptor": [
                "mitigation",
                "impact",
                "references",
                "component_name",
                "component_version",
                "unique_id_from_tool",
                "planned_remediation_date",
                "business_criticality (product)",
                "platform (product)",
                "lifecycle (product)",
            ],
        }
        write_credentials(payload)
        log("DefectDojo seed complete.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
