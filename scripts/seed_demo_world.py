#!/usr/bin/env python3
"""Populate RAPTOR with a production-looking demo world.

Creates users of every role, several applications, environments, hosts,
DNS zones, waves (open / started / closed), findings, occurrences, ACL,
shared hosts, tickets, and notebook notes — with dates spread across
many months so dashboards and weekly charts look inhabited.

Run inside the app container (scripts/ are not in the image):

    ./scripts/seed_demo_world.sh
    ./scripts/seed_demo_world.sh --verify

All demo users (and awadmin) use password 123.

Do not run this against a real production database.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import bcrypt

from app.config import DB_PATH
from app.integrations.db.connection import IntegrityError, ROW_AS_DICT, get_db_connection
from app.repositories import (
    applications_repository,
    environments_repository,
    pentest_findings_repository,
    phase2b_repository,
)
from app.repositories.admin_users_repository import update_admin_password
from app.repositories.records_mutation_repository import create_manual_record
from app.services.phase2b_service import close_wave as close_wave_svc
from app.services.phase2b_service import create_wave as create_wave_svc
from app.services.phase2b_service import start_wave as start_wave_svc
from app.services.user_admin_service import add_user_to_system

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("seed_demo_world")

PASSWORD = "123"
RNG = random.Random(42)
UTC = timezone.utc
NOW = datetime(2026, 8, 19, 15, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

USERS: List[Dict[str, str]] = [
    {"username": "nina.vale", "email": "nina.vale@raptor-demo.local", "role": "pentester", "full_name": "Nina Vale"},
    {"username": "jordan.cho", "email": "jordan.cho@raptor-demo.local", "role": "pentester", "full_name": "Jordan Cho"},
    {"username": "samir.okonkwo", "email": "samir.okonkwo@raptor-demo.local", "role": "pentester", "full_name": "Samir Okonkwo"},
    {"username": "lena.brooks", "email": "lena.brooks@raptor-demo.local", "role": "pentester", "full_name": "Lena Brooks"},
    {"username": "marco.stein", "email": "marco.stein@raptor-demo.local", "role": "pentester", "full_name": "Marco Stein"},
    {"username": "priya.shah", "email": "priya.shah@raptor-demo.local", "role": "pentester", "full_name": "Priya Shah"},
    {"username": "owen.clarke", "email": "owen.clarke@raptor-demo.local", "role": "pentester", "full_name": "Owen Clarke"},
    {"username": "yasmin.farouk", "email": "yasmin.farouk@raptor-demo.local", "role": "pentester", "full_name": "Yasmin Farouk"},
    {"username": "hana.reid", "email": "hana.reid@raptor-demo.local", "role": "manager", "full_name": "Hana Reid"},
    {"username": "david.okada", "email": "david.okada@raptor-demo.local", "role": "manager", "full_name": "David Okada"},
    {"username": "claire.mendez", "email": "claire.mendez@raptor-demo.local", "role": "manager", "full_name": "Claire Mendez"},
    {"username": "tom.becker", "email": "tom.becker@raptor-demo.local", "role": "user", "full_name": "Tom Becker"},
    {"username": "rina.solis", "email": "rina.solis@raptor-demo.local", "role": "user", "full_name": "Rina Solis"},
    {"username": "paul.nguyen", "email": "paul.nguyen@raptor-demo.local", "role": "user", "full_name": "Paul Nguyen"},
    {"username": "amira.hassan", "email": "amira.hassan@raptor-demo.local", "role": "user", "full_name": "Amira Hassan"},
    {"username": "lucia.petrova", "email": "lucia.petrova@raptor-demo.local", "role": "user", "full_name": "Lucia Petrova"},
    {"username": "erik.nilsen", "email": "erik.nilsen@raptor-demo.local", "role": "user", "full_name": "Erik Nilsen"},
    {"username": "sofia.alvarez", "email": "sofia.alvarez@raptor-demo.local", "role": "user", "full_name": "Sofia Alvarez"},
]

PENTESTERS = [u["username"] for u in USERS if u["role"] == "pentester"]
MANAGERS = [u["username"] for u in USERS if u["role"] == "manager"]
APP_OWNERS = [u["username"] for u in USERS if u["role"] == "user"]

# ---------------------------------------------------------------------------
# Apps / hosts
# ---------------------------------------------------------------------------

HOST_KINDS = [
    ("www", "Public web application", "80,443"),
    ("api", "REST / GraphQL API", "443,8080"),
    ("admin", "Staff admin console", "443"),
    ("auth", "SSO and session broker", "443"),
    ("mobile", "Mobile BFF", "443"),
    ("static", "Static assets", "80,443"),
    ("db", "Primary database", "5432"),
    ("cache", "Cache cluster", "6379"),
    ("mq", "Message bus", "5672,9092"),
    ("internal", "Internal tooling", "22,443"),
    ("jobs", "Batch workers", "443"),
    ("vpn", "App VPN concentrator", "443,1194"),
]

ENV_HOST_SUFFIX = {
    "prod": "",
    "stg": "-stg",
    "pp": "-pp",
    "qa": "-qa",
    "dr": "-dr",
    "sandbox": "-sbx",
    "unassigned": "-orphan",
}

APPS: List[Dict[str, Any]] = [
    {
        "name": "Aether Pay",
        "domain": "aetherpay.com",
        "owner": "Payments Platform",
        "data_class": "PCI / restricted",
        "roe_link": "https://wiki.raptor-demo.local/roe/aether-pay",
        "cookie_domain": ".aetherpay.com",
        "idp": "Okta",
        "token_audience": "api.aetherpay.com",
        "app_lead": "tom.becker",
        "created_by": "hana.reid",
        "zone_notes": "Customer cardholder environment plus staging mirrors.",
        "extra_envs": [{"slug": "dr", "display_name": "Disaster Recovery", "is_production": True}],
        "acl_stg": ["owen.clarke", "yasmin.farouk"],
        "share_kind": "auth",
    },
    {
        "name": "Northwind Portal",
        "domain": "northwind.corp",
        "owner": "Corporate IT",
        "data_class": "internal",
        "roe_link": "https://wiki.raptor-demo.local/roe/northwind",
        "cookie_domain": ".northwind.corp",
        "idp": "Entra ID",
        "token_audience": "portal.northwind.corp",
        "app_lead": "rina.solis",
        "created_by": "david.okada",
        "zone_notes": "Employee portal and vendor extranet.",
        "extra_envs": [{"slug": "sandbox", "display_name": "Sandbox", "is_production": False}],
        "acl_stg": ["marco.stein"],
        "share_kind": None,
    },
    {
        "name": "Atlas IAM",
        "domain": "atlas-iam.corp",
        "owner": "Identity Engineering",
        "data_class": "restricted",
        "roe_link": "https://wiki.raptor-demo.local/roe/atlas-iam",
        "cookie_domain": ".atlas-iam.corp",
        "idp": "self-hosted",
        "token_audience": "sts.atlas-iam.corp",
        "app_lead": "paul.nguyen",
        "created_by": "claire.mendez",
        "zone_notes": "Workforce identity, MFA, and session broker.",
        "extra_envs": [],
        "acl_stg": ["priya.shah", "owen.clarke"],
        "share_kind": None,
    },
    {
        "name": "Helios Edge",
        "domain": "helios-edge.net",
        "owner": "Edge Delivery",
        "data_class": "public",
        "roe_link": "https://wiki.raptor-demo.local/roe/helios",
        "cookie_domain": ".helios-edge.net",
        "idp": "none",
        "token_audience": "edge.helios-edge.net",
        "app_lead": "amira.hassan",
        "created_by": "hana.reid",
        "zone_notes": "CDN control plane and origin shield.",
        "extra_envs": [],
        "acl_stg": ["yasmin.farouk"],
        "share_kind": None,
    },
    {
        "name": "Beacon Mobile",
        "domain": "beaconapp.io",
        "owner": "Consumer Apps",
        "data_class": "PII",
        "roe_link": "https://wiki.raptor-demo.local/roe/beacon",
        "cookie_domain": ".beaconapp.io",
        "idp": "Auth0",
        "token_audience": "api.beaconapp.io",
        "app_lead": "lucia.petrova",
        "created_by": "david.okada",
        "zone_notes": "iOS / Android BFF and marketing site.",
        "extra_envs": [],
        "acl_stg": ["lena.brooks"],
        "share_kind": None,
    },
    {
        "name": "Harbor Inventory",
        "domain": "harbor-wms.corp",
        "owner": "Supply Chain",
        "data_class": "internal",
        "roe_link": "https://wiki.raptor-demo.local/roe/harbor",
        "cookie_domain": ".harbor-wms.corp",
        "idp": "Entra ID",
        "token_audience": "wms.harbor-wms.corp",
        "app_lead": "erik.nilsen",
        "created_by": "claire.mendez",
        "zone_notes": "Warehouse management and vendor EDI.",
        "extra_envs": [],
        "acl_stg": ["samir.okonkwo"],
        "share_kind": None,
        "compact": True,
    },
]

WAVE_PLANS = [
    {
        "key": "fy25q4",
        "name": "FY25 Q4 — Annual",
        "opened": datetime(2025, 11, 3, 9, 0, tzinfo=UTC),
        "started": datetime(2025, 11, 4, 8, 30, tzinfo=UTC),
        "closed": datetime(2025, 12, 19, 17, 0, tzinfo=UTC),
        "envs": ["prod"],
        "notes": "Annual production assessment. Credential stuffing and payment flows in scope.",
        "finding_count": 10,
        "mix": ("fixed", "fixed", "fixed", "accepted", "not_affected", "retest", "open", "fixed", "fixed", "open"),
    },
    {
        "key": "fy26q1",
        "name": "FY26 Q1 — Revalidation",
        "opened": datetime(2026, 1, 12, 10, 0, tzinfo=UTC),
        "started": datetime(2026, 1, 13, 9, 0, tzinfo=UTC),
        "closed": datetime(2026, 3, 6, 16, 30, tzinfo=UTC),
        "envs": ["prod", "stg"],
        "notes": "Retest of Q4 plus staging parity. IdP change landed mid-wave.",
        "finding_count": 9,
        "mix": ("fixed", "fixed", "retest", "accepted", "open", "fixed", "not_affected", "fixed", "open"),
    },
    {
        "key": "fy26q2",
        "name": "FY26 Q2 — Pre-release",
        "opened": datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
        "started": datetime(2026, 4, 7, 8, 0, tzinfo=UTC),
        "closed": datetime(2026, 6, 12, 18, 0, tzinfo=UTC),
        "envs": ["stg", "qa"],
        "notes": "Feature-freeze testing before the summer cutover. QA included for the first time.",
        "finding_count": 8,
        "mix": ("fixed", "fixed", "retest", "open", "accepted", "fixed", "open", "fixed"),
    },
    {
        "key": "current",
        "name": "FY26 Q3 — Live",
        "opened": datetime(2026, 7, 6, 11, 0, tzinfo=UTC),
        "started": datetime(2026, 7, 7, 9, 15, tzinfo=UTC),
        "closed": None,
        "envs": ["prod", "stg"],
        "notes": "In-progress wave. Findings filed from the wave workspace only.",
        "finding_count": 11,
        "mix": ("open", "open", "draft", "retest", "open", "fixed", "open", "accepted", "open", "retest", "open"),
    },
    {
        "key": "planned",
        "name": "FY26 Q3 — QA follow-up",
        "opened": datetime(2026, 8, 11, 14, 0, tzinfo=UTC),
        "started": None,
        "closed": None,
        "envs": ["qa"],
        "notes": "Queued. Do not start until the live wave signs off on prod.",
        "finding_count": 0,
        "mix": (),
    },
]

COMPACT_WAVE_KEYS = {"fy26q2", "current", "planned"}

METRICS = {
    "critical": {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "C", "C": "H", "I": "H", "A": "H"},
    "high": {"AV": "N", "AC": "L", "PR": "L", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "N"},
    "high_xss": {"AV": "N", "AC": "L", "PR": "N", "UI": "R", "S": "C", "C": "L", "I": "L", "A": "N"},
    "medium": {"AV": "N", "AC": "L", "PR": "L", "UI": "N", "S": "U", "C": "L", "I": "L", "A": "N"},
    "low": {"AV": "N", "AC": "H", "PR": "L", "UI": "R", "S": "U", "C": "L", "I": "N", "A": "N"},
    "info": {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "N", "I": "N", "A": "N"},
}

FINDING_TEMPLATES = [
    {
        "title": "Unauthenticated SQL injection on search",
        "category": "SQL Injection",
        "score": 9.8,
        "metrics": METRICS["critical"],
        "auth": "none",
        "kind": "api",
        "body": "The `/search` endpoint concatenates the `q` parameter into a SQL WHERE clause. A single quote returns a database error; `UNION SELECT` dumps user emails.",
    },
    {
        "title": "Stored XSS in support ticket comments",
        "category": "Stored XSS",
        "score": 6.1,
        "metrics": METRICS["high_xss"],
        "auth": "session cookie",
        "kind": "www",
        "body": "Ticket comments render attacker HTML. A payload in the comment body executes in the agent console as the signed-in operator.",
    },
    {
        "title": "IDOR on invoice PDF download",
        "category": "IDOR",
        "score": 8.1,
        "metrics": METRICS["high"],
        "auth": "customer JWT",
        "kind": "api",
        "body": "`GET /invoices/{id}.pdf` authorizes on authentication only. Sequential IDs return other tenants' invoices.",
    },
    {
        "title": "SSRF via webhook test URL",
        "category": "Server-Side Request Forgery (SSRF)",
        "score": 8.6,
        "metrics": METRICS["high"],
        "auth": "staff session",
        "kind": "admin",
        "body": "The webhook tester fetches attacker-controlled URLs from the app VPC. `http://169.254.169.254/` returns cloud metadata.",
    },
    {
        "title": "Broken access control on role assignment",
        "category": "Broken Access Control",
        "score": 8.8,
        "metrics": METRICS["high"],
        "auth": "low-privilege user",
        "kind": "admin",
        "body": "`PUT /users/{id}/roles` is missing a server-side admin check. A standard user can grant themselves `payments.admin`.",
    },
    {
        "title": "Reflected XSS on login `next` parameter",
        "category": "Reflected XSS",
        "score": 6.1,
        "metrics": METRICS["high_xss"],
        "auth": "none",
        "kind": "auth",
        "body": "The login page echoes `next` into a JS redirect without encoding. A crafted URL executes in the IdP origin.",
    },
    {
        "title": "Weak password policy on self-service reset",
        "category": "Weak Password Policy",
        "score": 5.3,
        "metrics": METRICS["medium"],
        "auth": "reset token",
        "kind": "auth",
        "body": "Password reset accepts 6-character alphabetic passwords and does not check the breached-password list.",
    },
    {
        "title": "Open redirect after SSO callback",
        "category": "Open Redirect",
        "score": 4.7,
        "metrics": METRICS["medium"],
        "auth": "none",
        "kind": "auth",
        "body": "`redirect_uri` is not constrained to the allow-list. A phished login can bounce the session cookie to an attacker site.",
    },
    {
        "title": "Directory listing on `/static/backups/`",
        "category": "Directory Listing",
        "score": 5.3,
        "metrics": METRICS["medium"],
        "auth": "none",
        "kind": "static",
        "body": "nginx autoindex is enabled. SQL dumps from a 2025 restore drill are downloadable without auth.",
    },
    {
        "title": "Insecure file upload on KYC documents",
        "category": "Insecure File Upload",
        "score": 8.1,
        "metrics": METRICS["high"],
        "auth": "customer JWT",
        "kind": "www",
        "body": "Content-type is trusted. A `.html` file uploaded as `image/png` is later served inline from the documents CDN.",
    },
    {
        "title": "Command injection in report exporter",
        "category": "Command Injection",
        "score": 9.8,
        "metrics": METRICS["critical"],
        "auth": "staff session",
        "kind": "jobs",
        "body": "The CSV exporter shells out to `pandoc` with an unsanitized filename. `; id` runs as the worker user.",
    },
    {
        "title": "Missing MFA enrollment enforcement",
        "category": "Broken Authentication",
        "score": 6.5,
        "metrics": METRICS["medium"],
        "auth": "password only",
        "kind": "auth",
        "body": "Privileged users can skip MFA enrollment for 30 days. Several finance accounts never enrolled.",
    },
    {
        "title": "Clickjacking on payment confirmation",
        "category": "Clickjacking",
        "score": 4.3,
        "metrics": METRICS["low"],
        "auth": "session cookie",
        "kind": "www",
        "body": "`X-Frame-Options` and CSP `frame-ancestors` are absent on `/checkout/confirm`. The page frames in a hidden iframe.",
    },
    {
        "title": "Verbose stack traces on API 500s",
        "category": "Information Disclosure",
        "score": 3.1,
        "metrics": METRICS["low"],
        "auth": "none",
        "kind": "api",
        "body": "Unhandled exceptions return SQL, file paths, and internal hostnames in the JSON `trace` field.",
    },
    {
        "title": "Session fixation through `sid` query param",
        "category": "Session Fixation",
        "score": 6.5,
        "metrics": METRICS["medium"],
        "auth": "none",
        "kind": "www",
        "body": "The app accepts a pre-set `sid` and does not rotate it after login.",
    },
    {
        "title": "Path traversal in export archive",
        "category": "Path Traversal",
        "score": 7.5,
        "metrics": METRICS["high"],
        "auth": "staff session",
        "kind": "jobs",
        "body": "`../` in the export name writes outside the reports bucket. `/etc/passwd` was retrieved in QA.",
    },
    {
        "title": "CSRF on beneficiary create",
        "category": "Cross-Site Request Forgery (CSRF)",
        "score": 6.5,
        "metrics": METRICS["medium"],
        "auth": "session cookie",
        "kind": "www",
        "body": "State-changing POST lacks a CSRF token and SameSite is `None`. A third-party page can add a payout beneficiary.",
    },
    {
        "title": "Default credentials on cache admin",
        "category": "Broken Authentication",
        "score": 7.2,
        "metrics": METRICS["high"],
        "auth": "none",
        "kind": "cache",
        "body": "The cache UI still has `admin` / `admin` on the staging and QA listeners.",
    },
]

TICKET_PREFIX = {
    "Aether Pay": "PAY",
    "Northwind Portal": "NWP",
    "Atlas IAM": "IAM",
    "Helios Edge": "HEL",
    "Beacon Mobile": "BCN",
    "Harbor Inventory": "HRB",
}


def ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S%z")


def hash_password() -> bytes:
    return bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt())


def execute(sql: str, params: Sequence[Any] = ()) -> None:
    with get_db_connection(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(sql, tuple(params))
        conn.commit()


def fetchall(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with get_db_connection(DB_PATH) as conn:
        conn.row_factory = ROW_AS_DICT
        c = conn.cursor()
        c.execute(sql, tuple(params))
        return [dict(row) for row in c.fetchall() or []]


def fetchone(sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def user_exists(username: str) -> bool:
    return fetchone("SELECT 1 AS ok FROM allowed_users WHERE username = ?", (username,)) is not None


def app_by_name(name: str) -> Optional[Dict[str, Any]]:
    return fetchone("SELECT * FROM applications WHERE name = ?", (name,))


def env_map(app_id: int) -> Dict[str, Dict[str, Any]]:
    return {str(env["slug"]): env for env in environments_repository.fetch_environments(app_id)}


def load_categories() -> Dict[str, str]:
    rows = fetchall("SELECT id, name FROM vuln_categories")
    return {str(row["name"]): str(row["id"]) for row in rows}


def pick_members(app_index: int, size: int = 3) -> List[str]:
    rotated = PENTESTERS[app_index % len(PENTESTERS) :] + PENTESTERS[: app_index % len(PENTESTERS)]
    return rotated[:size]


def host_fqdn(kind: str, domain: str, slug: str) -> str:
    suffix = ENV_HOST_SUFFIX.get(slug, f"-{slug}")
    return f"{kind}{suffix}.{domain}"


def host_ip(app_index: int, env_index: int, host_index: int) -> str:
    return f"10.{20 + app_index}.{10 + env_index}.{20 + host_index}"


def jitter(anchor: datetime, spread_days: int) -> datetime:
    if spread_days <= 0:
        return anchor
    delta = timedelta(
        days=RNG.randint(0, spread_days),
        hours=RNG.randint(8, 18),
        minutes=RNG.randint(0, 59),
    )
    return anchor + delta


def seed_admin() -> None:
    log.info("Setting awadmin password to %s", PASSWORD)
    result = update_admin_password(PASSWORD)
    log.info("  awadmin: %s", result)


def seed_users() -> None:
    log.info("Creating %s demo users (password=%s)", len(USERS), PASSWORD)
    for user in USERS:
        if user_exists(user["username"]):
            log.info("  %s (%s) — exists", user["username"], user["role"])
            continue
        try:
            add_user_to_system(
                username=user["username"],
                email=user["email"],
                role=user["role"],
                auth_type="local",
                password_hash=hash_password(),
                must_reset=0,
                permissions=[],
                is_service_account=False,
                full_name=user["full_name"],
            )
            log.info("  %s (%s) — created", user["username"], user["role"])
        except (IntegrityError, ValueError):
            log.info("  %s — already exists", user["username"])


def ensure_app(spec: Dict[str, Any]) -> Tuple[int, bool]:
    existing = app_by_name(spec["name"])
    if existing:
        log.info("  app %s — exists (id=%s), skipping rebuild", spec["name"], existing["id"])
        return int(existing["id"]), False
    app_id = applications_repository.create_application(spec["name"], spec["created_by"])
    if not app_id:
        raise RuntimeError(f"Failed to create application {spec['name']}")
    applications_repository.update_application(
        app_id,
        spec["name"],
        extra_fields={
            "owner": spec["owner"],
            "data_class": spec["data_class"],
            "roe_link": spec["roe_link"],
            "cookie_domain": spec["cookie_domain"],
            "idp": spec["idp"],
            "token_audience": spec["token_audience"],
            "app_lead": spec["app_lead"],
        },
    )
    created = datetime(2025, 6, 1, 12, 0, tzinfo=UTC) + timedelta(days=APPS.index(spec) * 11)
    execute("UPDATE applications SET created_at = ? WHERE id = ?", (created, app_id))
    log.info("  app %s — created id=%s", spec["name"], app_id)
    return int(app_id), True


def seed_extra_envs(app_id: int, spec: Dict[str, Any]) -> None:
    known = env_map(app_id)
    for extra in spec.get("extra_envs") or []:
        if extra["slug"] in known:
            continue
        environments_repository.create_environment(
            app_id,
            {
                "slug": extra["slug"],
                "display_name": extra["display_name"],
                "is_production": extra.get("is_production", False),
                "include_in_exec_report": extra.get("is_production", False),
            },
        )
    envs = env_map(app_id)
    for slug, env in envs.items():
        if slug == "unassigned":
            continue
        environments_repository.update_environment(
            app_id,
            int(env["id"]),
            {
                "allow_destructive": slug in {"stg", "qa", "sandbox"},
                "max_concurrent_scans": 3 if slug == "prod" else 2,
                "roe_text": (
                    f"Standing rules of engagement for {spec['name']} / {env['display_name']}. "
                    "No production data exfil. Destructive tests only where allow_destructive is on. "
                    "Contact the app lead before touching payment or identity cutovers."
                ),
                "contacts": f"{spec['app_lead']}, {spec['created_by']}",
                "data_class": spec["data_class"],
                "in_scope_urls": f"https://*.{spec['domain']}",
                "out_of_scope_urls": "https://status.*, https://vendor-sso.*",
                "creds_vault_pointer": f"vault://{spec['name'].lower().replace(' ', '-')}/{slug}",
                "test_window": "Mon–Thu 09:00–18:00 local" if slug == "prod" else "anytime with Slack ping",
                "include_in_exec_report": slug in {"prod", "stg"} or bool(env.get("is_production")),
            },
        )


def seed_hosts(app_id: int, spec: Dict[str, Any], app_index: int) -> Dict[str, List[Dict[str, Any]]]:
    envs = env_map(app_id)
    compact = bool(spec.get("compact"))
    kinds = HOST_KINDS[:8] if compact else HOST_KINDS
    env_slugs = [slug for slug in ("prod", "stg", "pp", "qa") if slug in envs]
    for extra in spec.get("extra_envs") or []:
        if extra["slug"] in envs and extra["slug"] not in env_slugs:
            env_slugs.append(extra["slug"])
    by_slug: Dict[str, List[Dict[str, Any]]] = {slug: [] for slug in envs}
    created_at = datetime(2025, 8, 1, 10, 0, tzinfo=UTC) + timedelta(days=app_index * 5)

    for env_index, slug in enumerate(env_slugs):
        env = envs[slug]
        take = kinds if slug in {"prod", "stg"} else kinds[:6]
        if slug in {"dr", "sandbox"}:
            take = kinds[:4]
        for host_index, (kind, description, ports) in enumerate(take):
            name = host_fqdn(kind, spec["domain"], slug)
            existing = fetchone("SELECT id, name FROM records WHERE LOWER(name) = LOWER(?)", (name,))
            if existing:
                record_id = int(existing["id"])
            else:
                created = create_manual_record(
                    name=name,
                    ip_address=host_ip(app_index, env_index, host_index),
                    application_owner=spec["owner"],
                    maintainer=spec["app_lead"],
                    description=f"{description} for {spec['name']} ({env['display_name']})",
                    open_ports=ports,
                    application_id=app_id,
                    username=spec["created_by"],
                    environment_id=int(env["id"]),
                )
                record_id = int(created["id"])
            in_scope = not (kind in {"vpn", "db"} and slug == "prod" and host_index % 5 == 0)
            applications_repository.assign_hosts(app_id, [record_id], int(env["id"]), in_scope=in_scope)
            stamp = created_at + timedelta(days=env_index * 3 + host_index)
            execute(
                """
                UPDATE records
                SET creation_date = ?, last_modification_date = ?
                WHERE id = ?
                """,
                (stamp, stamp + timedelta(days=20), record_id),
            )
            by_slug[slug].append({"id": record_id, "name": name, "kind": kind, "env_id": int(env["id"])})

    unassigned = envs.get("unassigned")
    if unassigned:
        for host_index, kind in enumerate(("legacy", "import")):
            name = f"{kind}-unfiled.{spec['domain']}"
            existing = fetchone("SELECT id FROM records WHERE LOWER(name) = LOWER(?)", (name,))
            if existing:
                record_id = int(existing["id"])
            else:
                created = create_manual_record(
                    name=name,
                    ip_address=host_ip(app_index, 9, host_index),
                    application_owner=spec["owner"],
                    maintainer=spec["app_lead"],
                    description="Imported from DNS, not yet filed into an environment.",
                    open_ports="443",
                    application_id=app_id,
                    username=spec["created_by"],
                    environment_id=int(unassigned["id"]),
                )
                record_id = int(created["id"])
            applications_repository.assign_hosts(app_id, [record_id], int(unassigned["id"]), in_scope=False)
            by_slug["unassigned"].append(
                {"id": record_id, "name": name, "kind": kind, "env_id": int(unassigned["id"])}
            )
    return by_slug


def seed_zone(app_id: int, spec: Dict[str, Any]) -> None:
    suffix = spec["domain"]
    existing = fetchone("SELECT id FROM dns_zones WHERE suffix = ?", (suffix,))
    if existing:
        return
    try:
        phase2b_repository.create_zone(suffix, spec["name"], app_id, spec.get("zone_notes") or "")
    except IntegrityError:
        return


def seed_acl(app_id: int, spec: Dict[str, Any], app_index: int) -> None:
    envs = env_map(app_id)
    members = pick_members(app_index)
    stg_names = sorted({*members, *(spec.get("acl_stg") or [])})
    stg = envs.get("stg")
    if stg and stg_names:
        phase2b_repository.replace_acl(int(stg["id"]), stg_names)
    qa = envs.get("qa")
    if qa:
        qa_names = sorted({members[-1], *((spec.get("acl_stg") or [])[:1] or members[:1])})
        phase2b_repository.replace_acl(int(qa["id"]), qa_names)


def backdate_wave(wave_id: int, opened: datetime, started: Optional[datetime], closed: Optional[datetime]) -> None:
    execute(
        """
        UPDATE engagement_waves
        SET opened_at = ?,
            started_at = ?,
            closed_at = ?
        WHERE id = ?
        """,
        (opened, started, closed, wave_id),
    )


def hosts_for_env_slugs(by_slug: Dict[str, List[Dict[str, Any]]], slugs: Sequence[str]) -> List[Dict[str, Any]]:
    hosts: List[Dict[str, Any]] = []
    seen = set()
    for slug in slugs:
        for host in by_slug.get(slug) or []:
            if host["id"] in seen:
                continue
            seen.add(host["id"])
            hosts.append(host)
    return hosts


def pick_host(hosts: Sequence[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    for host in hosts:
        if host.get("kind") == kind:
            return host
    return hosts[0]


def decorate_pentest(hosts: Sequence[Dict[str, Any]], members: Sequence[str], wave_started: Optional[datetime]) -> None:
    if not hosts:
        return
    for index, host in enumerate(hosts):
        tester = members[index % len(members)] if members else PENTESTERS[0]
        start = (wave_started or NOW) + timedelta(days=index % 4)
        notes = (
            f"## {host['name']}\n\n"
            f"- Tester: `{tester}`\n"
            "- Auth: staff SSO + one break-glass local account\n"
            "- Notes: cookie flags look fine on the marketing host; API still missing HSTS on the admin vhost.\n\n"
            "### Repro stash\n\n"
            "Burp project on the shared drive. SSRF payloads in `~/engagements/current/`.\n"
        )
        execute(
            """
            UPDATE pentest_data
            SET tested_by = ?,
                notes = ?,
                test_start_date = ?,
                open_ports = COALESCE(NULLIF(open_ports, ''), '443')
            WHERE record_id = ?
            """,
            (tester, notes, start.date().isoformat(), host["id"]),
        )


def backdate_finding(
    finding_id: str,
    created: datetime,
    occurrences: Sequence[Tuple[int, str, datetime]],
) -> None:
    execute(
        """
        UPDATE pentest_findings
        SET created_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (created, occurrences[-1][2] if occurrences else created, finding_id),
    )
    for record_id, _status, changed in occurrences:
        execute(
            """
            UPDATE finding_occurrences
            SET created_at = ?,
                updated_at = ?,
                status_changed_at = ?
            WHERE finding_id = ? AND record_id = ?
            """,
            (created, changed, changed, finding_id, record_id),
        )


def seed_finding(
    *,
    app_id: int,
    spec: Dict[str, Any],
    wave: Dict[str, Any],
    hosts: Sequence[Dict[str, Any]],
    template: Dict[str, Any],
    status: str,
    categories: Dict[str, str],
    created: datetime,
    closed_at: Optional[datetime],
    author: str,
    members: Sequence[str],
    ticket_n: int,
) -> None:
    if not hosts:
        return
    primary = pick_host(hosts, template["kind"])
    extra = []
    if len(hosts) > 1 and RNG.random() < 0.45:
        candidate = hosts[(hosts.index(primary) + 1) % len(hosts)]
        if candidate["id"] != primary["id"]:
            extra.append(candidate)

    category_name = template["category"]
    if category_name not in categories:
        category_name = next(iter(categories), template["category"])
    ticket = ""
    if status in {"open", "retest", "fixed", "accepted"} and RNG.random() < 0.7:
        ticket = f"https://jira.raptor-demo.local/browse/{TICKET_PREFIX[spec['name']]}-{ticket_n}"

    payload = {
        "title": f"{template['title']} ({spec['name']})",
        "categoryId": categories.get(category_name, ""),
        "categoryName": category_name,
        "description": (
            f"{template['body']}\n\n"
            f"**Host:** `{primary['name']}`\n"
            f"**Wave:** {wave.get('name')}\n"
            f"**Auth context:** {template['auth']}\n\n"
            "### Impact\n\n"
            "Confirmed in this environment with a non-destructive proof. Evidence screenshots live on the finding.\n"
        ),
        "created_by": author,
        "application_id": app_id,
        "status": "open" if status == "draft" else status,
        "source": "human",
        "baseScore": template["score"],
        "metrics": template["metrics"],
        "auth_context": template["auth"],
        "ticket_url": ticket,
        "discovered_wave_id": int(wave["id"]),
        "collaborators": list(members),
    }
    finding_id = pentest_findings_repository.insert_finding(int(primary["id"]), payload)
    extra_ids = [int(item["id"]) for item in extra]
    if extra_ids:
        pentest_findings_repository.attach_occurrences(finding_id, extra_ids)

    changed = created
    if status in {"fixed", "accepted", "not_affected", "retest"}:
        horizon = closed_at or NOW
        span = max(1, (horizon - created).days)
        changed = created + timedelta(days=min(span, RNG.randint(3, max(4, span))))
        if changed > horizon:
            changed = horizon
    pentest_findings_repository.set_occurrence_status(finding_id, int(primary["id"]), status)
    occ_rows: List[Tuple[int, str, datetime]] = [(int(primary["id"]), status, changed)]
    for item in extra:
        extra_status = status
        pentest_findings_repository.set_occurrence_status(finding_id, int(item["id"]), extra_status)
        occ_rows.append((int(item["id"]), extra_status, changed))
        if extra:
            execute(
                """
                UPDATE finding_occurrences
                SET primary_url = ?, evidence_note = ?
                WHERE finding_id = ? AND record_id = ?
                """,
                (
                    f"https://{item['name']}/",
                    f"Same class of issue on {item['name']}.",
                    finding_id,
                    int(item["id"]),
                ),
            )
    backdate_finding(finding_id, created, occ_rows)


def seed_waves(
    app_id: int,
    spec: Dict[str, Any],
    app_index: int,
    by_slug: Dict[str, List[Dict[str, Any]]],
    categories: Dict[str, str],
) -> None:
    envs = env_map(app_id)
    members = pick_members(app_index)
    plans = WAVE_PLANS
    if spec.get("compact"):
        plans = [plan for plan in WAVE_PLANS if plan["key"] in COMPACT_WAVE_KEYS]
    ticket_n = 1000 + app_index * 80

    for plan in plans:
        env_ids = []
        for slug in plan["envs"]:
            if slug in envs:
                env_ids.append(int(envs[slug]["id"]))
        if not env_ids:
            continue
        payload, status = create_wave_svc(
            app_id,
            {
                "name": plan["name"],
                "env_ids": env_ids,
                "notes": plan["notes"],
                "members": members,
            },
            members[0],
        )
        if status >= 400:
            raise RuntimeError(f"create_wave failed for {spec['name']} {plan['name']}: {payload}")
        wave = payload["wave"]
        wave_id = int(wave["id"])

        if plan["started"]:
            started, start_status = start_wave_svc(app_id, wave_id)
            if start_status >= 400:
                raise RuntimeError(f"start_wave failed: {started}")
            wave = started["wave"]

        live = hosts_for_env_slugs(by_slug, plan["envs"])
        if live and plan["started"]:
            out = [host["id"] for host in live if host.get("kind") in {"vpn"}][:2]
            if out:
                phase2b_repository.set_wave_host_scope(wave_id, out, False)
            decorate_pentest(live, members, plan["started"])

        if plan["finding_count"] and plan["started"]:
            window_end = plan["closed"] or NOW
            span_days = max(3, (window_end - plan["started"]).days - 2)
            for index in range(plan["finding_count"]):
                template = FINDING_TEMPLATES[(app_index * 3 + index) % len(FINDING_TEMPLATES)]
                status_name = plan["mix"][index % len(plan["mix"])]
                created = jitter(plan["started"] + timedelta(days=1), span_days)
                if created >= window_end:
                    created = window_end - timedelta(days=1, hours=3)
                author = members[index % len(members)]
                ticket_n += 1
                seed_finding(
                    app_id=app_id,
                    spec=spec,
                    wave=wave,
                    hosts=live,
                    template=template,
                    status=status_name,
                    categories=categories,
                    created=created,
                    closed_at=plan["closed"],
                    author=author,
                    members=members,
                    ticket_n=ticket_n,
                )

        if plan["closed"]:
            closed, close_status = close_wave_svc(app_id, wave_id)
            if close_status >= 400:
                raise RuntimeError(f"close_wave failed: {closed}")

        backdate_wave(wave_id, plan["opened"], plan["started"], plan["closed"])
        log.info("    wave %s (%s)", plan["name"], "closed" if plan["closed"] else ("started" if plan["started"] else "not started"))


def seed_shared_host(apps_created: List[Tuple[Dict[str, Any], int, Dict[str, List[Dict[str, Any]]]]]) -> None:
    if len(apps_created) < 2:
        return
    owner_spec, owner_id, owner_hosts = apps_created[0]
    _, consumer_id, _ = apps_created[2] if len(apps_created) > 2 else apps_created[1]
    prod = owner_hosts.get("prod") or []
    auth = next((host for host in prod if host.get("kind") == owner_spec.get("share_kind")), None)
    if not auth:
        return
    phase2b_repository.share_host(int(auth["id"]), owner_id, consumer_id)
    log.info("  shared %s from %s → app %s", auth["name"], owner_spec["name"], consumer_id)


def verify() -> Dict[str, Any]:
    stats = {
        "users": fetchone("SELECT COUNT(*) AS n FROM allowed_users")["n"],
        "users_pentester": fetchone("SELECT COUNT(*) AS n FROM allowed_users WHERE role = 'pentester'")["n"],
        "users_manager": fetchone("SELECT COUNT(*) AS n FROM allowed_users WHERE role = 'manager'")["n"],
        "users_user": fetchone("SELECT COUNT(*) AS n FROM allowed_users WHERE role = 'user'")["n"],
        "apps": fetchone("SELECT COUNT(*) AS n FROM applications")["n"],
        "environments": fetchone("SELECT COUNT(*) AS n FROM environments")["n"],
        "hosts": fetchone("SELECT COUNT(*) AS n FROM records")["n"],
        "in_scope_hosts": fetchone("SELECT COUNT(*) AS n FROM records WHERE COALESCE(in_scope, FALSE)")["n"],
        "waves": fetchone("SELECT COUNT(*) AS n FROM engagement_waves")["n"],
        "waves_open": fetchone("SELECT COUNT(*) AS n FROM engagement_waves WHERE status = 'open'")["n"],
        "waves_closed": fetchone("SELECT COUNT(*) AS n FROM engagement_waves WHERE status = 'closed'")["n"],
        "waves_started": fetchone("SELECT COUNT(*) AS n FROM engagement_waves WHERE started_at IS NOT NULL")["n"],
        "findings": fetchone("SELECT COUNT(*) AS n FROM pentest_findings")["n"],
        "occurrences": fetchone("SELECT COUNT(*) AS n FROM finding_occurrences")["n"],
        "zones": fetchone("SELECT COUNT(*) AS n FROM dns_zones")["n"],
        "acl_rows": fetchone("SELECT COUNT(*) AS n FROM environment_acl")["n"],
    }
    by_status = fetchall("SELECT status, COUNT(*) AS n FROM pentest_findings GROUP BY status ORDER BY n DESC")
    occ_status = fetchall("SELECT status, COUNT(*) AS n FROM finding_occurrences GROUP BY status ORDER BY n DESC")
    oldest = fetchone("SELECT MIN(created_at) AS d FROM pentest_findings")
    newest = fetchone("SELECT MAX(created_at) AS d FROM pentest_findings")
    log.info("Demo world counts:")
    for key, value in stats.items():
        log.info("  %-18s %s", key, value)
    log.info("  finding status     %s", {row["status"]: row["n"] for row in by_status})
    log.info("  occurrence status  %s", {row["status"]: row["n"] for row in occ_status})
    log.info("  findings span      %s → %s", oldest and oldest.get("d"), newest and newest.get("d"))

    missing = [key for key, value in stats.items() if int(value or 0) <= 0]
    critical = {"users", "apps", "environments", "hosts", "waves", "findings", "occurrences"}
    failed = [key for key in missing if key in critical]
    if failed:
        raise SystemExit(f"Seed verification failed, empty: {', '.join(failed)}")
    return stats


def seed() -> None:
    log.info("Seeding demo world into %s", (DB_PATH or "")[:32] + "…")
    seed_admin()
    seed_users()
    categories = load_categories()
    if not categories:
        log.warning("vuln_categories is empty; findings will still insert by name")
    created_apps: List[Tuple[Dict[str, Any], int, Dict[str, List[Dict[str, Any]]]]] = []
    for app_index, spec in enumerate(APPS):
        log.info("Application %s", spec["name"])
        app_id, fresh = ensure_app(spec)
        seed_extra_envs(app_id, spec)
        by_slug = seed_hosts(app_id, spec, app_index)
        seed_zone(app_id, spec)
        seed_acl(app_id, spec, app_index)
        if fresh:
            seed_waves(app_id, spec, app_index, by_slug, categories)
        else:
            log.info("  waves left untouched (app already existed)")
        created_apps.append((spec, app_id, by_slug))
    seed_shared_host(created_apps)
    verify()
    log.info("Done. Log in as awadmin / nina.vale / hana.reid / tom.becker — password %s", PASSWORD)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a production-looking RAPTOR demo world")
    parser.add_argument("--verify", action="store_true", help="Print counts only; do not insert")
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    seed()


if __name__ == "__main__":
    main()
