#!/usr/bin/env python3
"""Unattended Jira 9.x setup plus RAPTOR lab project, screens, and extra fields."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

JIRA_URL = os.environ.get("JIRA_URL", "http://jira:8080").rstrip("/")
PUBLIC_URL = os.environ.get("JIRA_PUBLIC_URL", "http://localhost:8090").rstrip("/")
ADMIN_USER = os.environ.get("JIRA_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("JIRA_ADMIN_PASSWORD", "RaptoR!jira1")
ADMIN_EMAIL = os.environ.get("JIRA_ADMIN_EMAIL", "admin@raptor.local")
LICENSE_FILE = os.environ.get("JIRA_LICENSE_FILE", "/license/jira-timebomb.lic")
OUT_DIR = os.environ.get("SEED_OUT_DIR", "/out")
SETUP_TIMEOUT = int(os.environ.get("JIRA_SETUP_TIMEOUT", "900"))
WIZARD_TIMEOUT = int(os.environ.get("JIRA_WIZARD_TIMEOUT", "600"))

PROJECTS = [
    {
        "key": "SEC",
        "name": "Security Findings",
        "description": "Company-managed kanban for RAPTOR finding tickets.",
        "template": "com.pyxis.greenhopper.jira:gh-kanban-template",
        "type": "software",
    },
    {
        "key": "APP",
        "name": "Application Backlog",
        "description": "Second project so RAPTOR can choose among ticket templates.",
        "template": "com.pyxis.greenhopper.jira:gh-scrum-template",
        "type": "software",
    },
]
TEMPLATE_FALLBACKS = [
    "com.pyxis.greenhopper.jira:gh-kanban-template",
    "com.pyxis.greenhopper.jira:gh-scrum-template",
    "com.atlassian.jira-core-project-templates:jira-core-project-management",
    "com.atlassian.jira-core-project-templates:jira-core-task-management",
]

CUSTOM_FIELDS = [
    {
        "name": "Dev Team",
        "description": "Owning engineering team. RAPTOR has no equivalent field — map as Ask when sending.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searcher": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["Red Team", "AppSec", "Platform", "Cloud"],
    },
    {
        "name": "Project Tag",
        "description": "Compliance / scope tags. RAPTOR has no equivalent — map as Ask when sending.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
        "searcher": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["PCI", "Internal", "External", "Production"],
    },
    {
        "name": "Remediation SLA",
        "description": "Fix-by window. RAPTOR has no SLA field — map as Ask when sending.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searcher": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["7 days", "30 days", "90 days", "Next release"],
    },
    {
        "name": "Business Owner",
        "description": "Named owner. RAPTOR has no business-owner field — leave as Ask or skip.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:textfield",
        "searcher": "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "options": [],
    },
    {
        "name": "Needs CAB",
        "description": "Change-advisory flag. RAPTOR has no CAB field — map as Ask when sending.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searcher": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["Yes", "No"],
    },
    {
        "name": "Affected CWE",
        "description": "CWE identifier. RAPTOR findings do not carry CWE — optional Ask field.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:textfield",
        "searcher": "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "options": [],
    },
]

COMPONENTS = ["Authentication", "API", "Cloud", "Client"]
VERSIONS = ["Current pentest"]

# Keep in sync with scripts/seed_demo_world.py (USERS + awadmin). Same lab password.
DEMO_USER_PASSWORD = os.environ.get("JIRA_DEMO_USER_PASSWORD", "RaptorDemo123!")
DEMO_USERS: List[Dict[str, str]] = [
    {"username": "awadmin", "email": "awadmin@raptor-demo.local", "display_name": "RAPTOR Admin", "role": "admin"},
    {"username": "nina.vale", "email": "nina.vale@raptor-demo.local", "display_name": "Nina Vale", "role": "pentester"},
    {"username": "jordan.cho", "email": "jordan.cho@raptor-demo.local", "display_name": "Jordan Cho", "role": "pentester"},
    {"username": "samir.okonkwo", "email": "samir.okonkwo@raptor-demo.local", "display_name": "Samir Okonkwo", "role": "pentester"},
    {"username": "lena.brooks", "email": "lena.brooks@raptor-demo.local", "display_name": "Lena Brooks", "role": "pentester"},
    {"username": "marco.stein", "email": "marco.stein@raptor-demo.local", "display_name": "Marco Stein", "role": "pentester"},
    {"username": "priya.shah", "email": "priya.shah@raptor-demo.local", "display_name": "Priya Shah", "role": "pentester"},
    {"username": "owen.clarke", "email": "owen.clarke@raptor-demo.local", "display_name": "Owen Clarke", "role": "pentester"},
    {"username": "yasmin.farouk", "email": "yasmin.farouk@raptor-demo.local", "display_name": "Yasmin Farouk", "role": "pentester"},
    {"username": "hana.reid", "email": "hana.reid@raptor-demo.local", "display_name": "Hana Reid", "role": "manager"},
    {"username": "david.okada", "email": "david.okada@raptor-demo.local", "display_name": "David Okada", "role": "manager"},
    {"username": "claire.mendez", "email": "claire.mendez@raptor-demo.local", "display_name": "Claire Mendez", "role": "manager"},
    {"username": "tom.becker", "email": "tom.becker@raptor-demo.local", "display_name": "Tom Becker", "role": "user"},
    {"username": "rina.solis", "email": "rina.solis@raptor-demo.local", "display_name": "Rina Solis", "role": "user"},
    {"username": "paul.nguyen", "email": "paul.nguyen@raptor-demo.local", "display_name": "Paul Nguyen", "role": "user"},
    {"username": "amira.hassan", "email": "amira.hassan@raptor-demo.local", "display_name": "Amira Hassan", "role": "user"},
    {"username": "lucia.petrova", "email": "lucia.petrova@raptor-demo.local", "display_name": "Lucia Petrova", "role": "user"},
    {"username": "erik.nilsen", "email": "erik.nilsen@raptor-demo.local", "display_name": "Erik Nilsen", "role": "user"},
    {"username": "sofia.alvarez", "email": "sofia.alvarez@raptor-demo.local", "display_name": "Sofia Alvarez", "role": "user"},
]
LICENSE_PRIORITY = {"pentester": 0, "manager": 1, "admin": 2, "user": 3}


def log(message: str) -> None:
    print(message, flush=True)


def load_license() -> str:
    env_license = (os.environ.get("JIRA_LICENSE") or "").strip()
    if env_license:
        return re.sub(r"\s+", "", env_license)
    with open(LICENSE_FILE, encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip() and not line.strip().startswith("#")]
    return "".join(lines)


def wait_status(client: httpx.Client, wanted: Tuple[str, ...], timeout: int) -> str:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            response = client.get("/status")
            last = (response.text or "")[:200]
            match = re.search(r'"state"\s*:\s*"([A-Z_]+)"', last, re.I)
            state = (match.group(1) if match else last).upper()
            log(f"Jira /status -> {state}")
            if state == "FIRST_RUN":
                state = "SETUP"
            if any(item == state or item in state for item in wanted):
                return state
        except httpx.HTTPError as exc:
            last = str(exc)
            log(f"Waiting for Jira: {exc}")
        time.sleep(5)
    raise SystemExit(f"Jira did not reach {wanted} within {timeout}s. Last: {last}")


def token_from(client: httpx.Client, html: str = "") -> str:
    cookie = client.cookies.get("atlassian.xsrf.token") or ""
    match = re.search(r'name="atl_token"\s+value="([^"]+)"', html or "")
    html_token = match.group(1) if match else ""
    return html_token or cookie


def post_form(client: httpx.Client, path: str, data: Dict[str, str], html: str = "") -> httpx.Response:
    payload = dict(data)
    payload.setdefault("atl_token", token_from(client, html))
    return client.post(
        path,
        data=payload,
        headers={"X-Atlassian-Token": "no-check", "Content-Type": "application/x-www-form-urlencoded"},
    )


def current_setup_page(client: httpx.Client) -> str:
    response = client.get("/")
    url = str(response.url)
    log(f"Jira landing -> {url} ({response.status_code})")
    return url


def run_setup_wizard(client: httpx.Client, license_key: str) -> None:
    if "RUNNING" in wait_status(client, ("SETUP", "RUNNING"), SETUP_TIMEOUT):
        log("Jira is already RUNNING; skipping setup wizard.")
        return

    wait_status(client, ("SETUP",), SETUP_TIMEOUT)
    landing = current_setup_page(client)
    html = client.get("/secure/SetupMode.jspa").text

    if "SetupMode" in landing or "SetupMode" in html or "setupOption" in html:
        log("Setup mode: classic")
        response = post_form(client, "/secure/SetupMode.jspa", {"setupOption": "classic"}, html)
        log(f"SetupMode -> {response.status_code} {response.url}")
        html = response.text
    else:
        log("Setup mode already decided.")

    landing = current_setup_page(client)
    if "SetupDatabase" in landing:
        log("Database page still visible; posting JDBC settings (env already configured).")
        response = post_form(
            client,
            "/secure/SetupDatabase.jspa",
            {
                "databaseOption": "external",
                "databaseType": "postgres72",
                "jdbcHostname": os.environ.get("JIRA_DB_HOST", "jira-db"),
                "jdbcPort": os.environ.get("JIRA_DB_PORT", "5432"),
                "jdbcDatabase": os.environ.get("JIRA_DB_NAME", "jira"),
                "jdbcSid": "",
                "jdbcUsername": os.environ.get("JIRA_DB_USER", "jira"),
                "jdbcPassword": os.environ.get("JIRA_DB_PASSWORD", "jira"),
                "schemaName": "public",
            },
            client.get("/secure/SetupDatabase.jspa").text,
        )
        log(f"SetupDatabase -> {response.status_code} {response.url}")

    html = client.get("/secure/SetupApplicationProperties.jspa").text
    log("Application properties")
    response = post_form(
        client,
        "/secure/SetupApplicationProperties.jspa",
        {
            "title": "RAPTOR Jira",
            "mode": "private",
            "baseURL": PUBLIC_URL,
            "nextStep": "true",
        },
        html,
    )
    log(f"SetupApplicationProperties -> {response.status_code} {response.url}")

    html = client.get("/secure/SetupLicense.jspa").text
    log("Validating license")
    client.post(
        "/secure/SetupLicense!validateLicense.jspa",
        data={"licenseToValidate": license_key},
        headers={"X-Atlassian-Token": "no-check", "Content-Type": "application/x-www-form-urlencoded"},
    )
    response = post_form(client, "/secure/SetupLicense.jspa", {"setupLicenseKey": license_key}, html)
    log(f"SetupLicense -> {response.status_code} {response.url}")
    if response.status_code >= 400 or "invalid" in (response.text or "").lower() and "setupLicense" in (response.text or ""):
        snippet = re.sub(r"\s+", " ", response.text or "")[:400]
        log(f"License response snippet: {snippet}")

    html = client.get("/secure/SetupAdminAccount.jspa").text
    log(f"Creating admin {ADMIN_USER}")
    response = post_form(
        client,
        "/secure/SetupAdminAccount.jspa",
        {
            "fullname": "RAPTOR Admin",
            "email": ADMIN_EMAIL,
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
            "confirm": ADMIN_PASSWORD,
        },
        html,
    )
    log(f"SetupAdminAccount -> {response.status_code} {response.url}")

    html = client.get("/secure/SetupMailNotifications.jspa").text
    log("Skipping mail")
    response = post_form(
        client,
        "/secure/SetupMailNotifications.jspa",
        {
            "noemail": "true",
            "analytics-enabled": "",
            "name": "admin",
            "from": "jira@raptor.local",
            "prefix": "[Jira]",
            "mailservertype": "smtp",
            "serverProvider": "custom",
            "serverName": "",
            "protocol": "smtp",
            "port": "",
            "timeout": "10000",
            "username": "",
            "password": "",
            "jndiLocation": "",
            "type": "smtp",
            "testingMailConnection": "false",
        },
        html,
    )
    log(f"SetupMailNotifications -> {response.status_code} {response.url}")
    wait_status(client, ("RUNNING",), WIZARD_TIMEOUT)


def basic_auth_client() -> httpx.Client:
    return httpx.Client(
        base_url=JIRA_URL,
        auth=(ADMIN_USER, ADMIN_PASSWORD),
        headers={"Accept": "application/json", "X-Atlassian-Token": "no-check", "User-Agent": "raptor-jira-seed"},
        timeout=60.0,
        follow_redirects=True,
    )


def wait_rest(client: httpx.Client, timeout: int = 300) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            response = client.get("/rest/api/2/serverInfo")
            if response.status_code == 200:
                info = response.json()
                log(f"REST ready: {info.get('version')} {info.get('serverTitle')}")
                return
            last = f"HTTP {response.status_code} {(response.text or '')[:120]}"
        except httpx.HTTPError as exc:
            last = str(exc)
        log(f"Waiting for REST: {last}")
        time.sleep(5)
    raise SystemExit(f"Jira REST never became ready: {last}")


def json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": (response.text or "")[:500], "status": response.status_code}


def api(client: httpx.Client, method: str, path: str, **kwargs) -> Tuple[int, Any]:
    response = client.request(method, path, **kwargs)
    return response.status_code, json_or_text(response)


def ensure_projects(client: httpx.Client) -> List[Dict[str, str]]:
    status, body = api(client, "GET", "/rest/api/2/project")
    existing = {item.get("key"): item for item in body} if isinstance(body, list) else {}
    created = []
    for spec in PROJECTS:
        if spec["key"] in existing:
            log(f"Project {spec['key']} already exists")
            created.append({"key": spec["key"], "name": existing[spec["key"]].get("name") or spec["name"]})
            continue
        payload = {
            "key": spec["key"],
            "name": spec["name"],
            "description": spec["description"],
            "projectTypeKey": spec["type"],
            "projectTemplateKey": spec["template"],
            "lead": ADMIN_USER,
        }
        status, body = api(client, "POST", "/rest/api/2/project", json=payload)
        if status >= 400:
            for template in TEMPLATE_FALLBACKS:
                payload["projectTemplateKey"] = template
                payload["projectTypeKey"] = "software" if "greenhopper" in template else "business"
                status, body = api(client, "POST", "/rest/api/2/project", json=payload)
                if status < 400:
                    log(f"Created project {spec['key']} with template {template}")
                    break
        if status >= 400:
            raise SystemExit(f"Could not create project {spec['key']}: {status} {body}")
        log(f"Created project {spec['key']}")
        created.append({"key": spec["key"], "name": spec["name"]})
    return created


def ensure_issue_type(client: httpx.Client, name: str, description: str) -> Optional[str]:
    status, body = api(client, "GET", "/rest/api/2/issuetype")
    rows = body if isinstance(body, list) else []
    for item in rows:
        if str(item.get("name") or "").lower() == name.lower():
            return str(item.get("id") or "")
    status, body = api(
        client,
        "POST",
        "/rest/api/2/issuetype",
        json={"name": name, "description": description, "type": "standard"},
    )
    if status >= 400:
        log(f"Could not create issue type {name}: {status} {body}")
        return None
    log(f"Created issue type {name}")
    return str((body or {}).get("id") or "")


def list_fields(client: httpx.Client) -> List[Dict[str, Any]]:
    status, body = api(client, "GET", "/rest/api/2/field")
    if status >= 400 or not isinstance(body, list):
        raise SystemExit(f"Could not list fields: {status} {body}")
    return body


def field_by_name(fields: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for item in fields:
        if str(item.get("name") or "").lower() == name.lower():
            return item
    return None


def create_custom_field(client: httpx.Client, spec: Dict[str, Any]) -> Dict[str, Any]:
    fields = list_fields(client)
    existing = field_by_name(fields, spec["name"])
    if existing:
        log(f"Custom field {spec['name']} already exists as {existing.get('id')}")
        return existing
    status, body = api(
        client,
        "POST",
        "/rest/api/2/field",
        json={
            "name": spec["name"],
            "description": spec["description"],
            "type": spec["type"],
            "searcherKey": spec["searcher"],
        },
    )
    if status >= 400 or not isinstance(body, dict):
        raise SystemExit(f"Could not create field {spec['name']}: {status} {body}")
    log(f"Created custom field {spec['name']} ({body.get('id')})")
    return body


def add_field_to_screens(client: httpx.Client, field_id: str) -> None:
    api(client, "POST", f"/rest/api/2/screens/addToDefault/{field_id}")
    status, body = api(client, "GET", "/rest/api/2/screens")
    screens = []
    if isinstance(body, dict):
        screens = body.get("screens") or body.get("values") or []
    elif isinstance(body, list):
        screens = body
    for screen in screens:
        screen_id = screen.get("id")
        if screen_id is None:
            continue
        t_status, tabs = api(client, "GET", f"/rest/api/2/screens/{screen_id}/tabs")
        if t_status >= 400 or not isinstance(tabs, list):
            continue
        for tab in tabs:
            tab_id = tab.get("id")
            if tab_id is None:
                continue
            api(
                client,
                "POST",
                f"/rest/api/2/screens/{screen_id}/tabs/{tab_id}/fields",
                json={"fieldId": field_id},
            )


def numeric_field_id(field_id: str) -> str:
    return str(field_id).replace("customfield_", "")


def add_options_rest(client: httpx.Client, field_id: str, options: List[str]) -> bool:
    context_paths = [
        f"/rest/api/2/field/{field_id}/context",
        f"/rest/api/2/customField/{numeric_field_id(field_id)}/contexts",
        f"/rest/api/3/field/{field_id}/context",
    ]
    contexts: List[Dict[str, Any]] = []
    for path in context_paths:
        status, body = api(client, "GET", path)
        if status >= 400:
            continue
        if isinstance(body, dict):
            contexts = body.get("values") or body.get("contexts") or []
        elif isinstance(body, list):
            contexts = body
        if contexts:
            break
    if not contexts:
        return False
    context_id = contexts[0].get("id")
    if context_id is None:
        return False
    payload = {"options": [{"value": value, "disabled": False} for value in options]}
    for path in (
        f"/rest/api/2/field/{field_id}/context/{context_id}/option",
        f"/rest/api/2/customField/{numeric_field_id(field_id)}/option",
        f"/rest/api/3/field/{field_id}/context/{context_id}/option",
    ):
        status, body = api(client, "POST", path, json=payload)
        if status < 400:
            log(f"Added options via {path}")
            return True
        log(f"Option REST {path} -> {status} {body}")
    return False


def session_client() -> httpx.Client:
    client = httpx.Client(
        base_url=JIRA_URL,
        headers={"User-Agent": "raptor-jira-seed", "X-Atlassian-Token": "no-check"},
        timeout=60.0,
        follow_redirects=True,
    )
    login = client.post("/rest/auth/1/session", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    if login.status_code >= 400:
        html = client.get("/login.jsp").text
        post_form(
            client,
            "/login.jsp",
            {
                "os_username": ADMIN_USER,
                "os_password": ADMIN_PASSWORD,
                "os_destination": "",
                "user_role": "",
                "login": "Log In",
            },
            html,
        )
    sudo_html = client.get("/secure/admin/WebSudoAuthenticate.jspa").text
    post_form(
        client,
        "/secure/admin/WebSudoAuthenticate.jspa",
        {
            "webSudoPassword": ADMIN_PASSWORD,
            "webSudoIsPost": "false",
            "webSudoDestination": "/secure/admin/ViewCustomFields.jspa",
            "os_cookie": "true",
        },
        sudo_html,
    )
    return client


def add_options_html(field_id: str, options: List[str]) -> bool:
    numeric = numeric_field_id(field_id)
    client = session_client()
    try:
        html = client.get(f"/secure/admin/ConfigureCustomField!default.jspa?customFieldId={numeric}").text
        config_ids = set(re.findall(r"fieldConfigId=(\d+)", html))
        config_ids.update(re.findall(r'name="fieldConfigId"\s+value="(\d+)"', html))
        if not config_ids:
            options_html = client.get(
                f"/secure/admin/EditCustomFieldOptions!default.jspa?customFieldId={numeric}"
            ).text
            config_ids.update(re.findall(r"fieldConfigId=(\d+)", options_html))
            html = options_html
        if not config_ids:
            log(f"No fieldConfigId in HTML for {field_id}")
            return False
        field_config_id = sorted(config_ids)[0]
        log(f"HTML fieldConfigId for {field_id} = {field_config_id}")
        added = 0
        for value in options:
            response = post_form(
                client,
                "/secure/admin/EditCustomFieldOptions!add.jspa",
                {"fieldConfigId": field_config_id, "addValue": value, "add": "Add"},
                html,
            )
            if response.status_code < 400:
                added += 1
                html = response.text
            else:
                log(f"HTML add option {value} -> {response.status_code}")
        return added == len(options)
    except Exception as exc:  # noqa: BLE001
        log(f"HTML options failed for {field_id}: {exc}")
        return False
    finally:
        client.close()


def add_options_sql(field_id: str, options: List[str]) -> bool:
    if psycopg is None:
        return False
    numeric = int(numeric_field_id(field_id))
    dsn = (
        f"host={os.environ.get('JIRA_DB_HOST', 'jira-db')} "
        f"port={os.environ.get('JIRA_DB_PORT', '5432')} "
        f"dbname={os.environ.get('JIRA_DB_NAME', 'jira')} "
        f"user={os.environ.get('JIRA_DB_USER', 'jira')} "
        f"password={os.environ.get('JIRA_DB_PASSWORD', 'jira')}"
    )
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fcsit.fieldconfiguration
                    FROM fieldconfigscheme fcs
                    JOIN fieldconfigschemeissuetype fcsit ON fcsit.fieldconfigscheme = fcs.id
                    WHERE fcs.fieldid = %s
                    LIMIT 1
                    """,
                    (field_id,),
                )
                row = cur.fetchone()
                if not row:
                    log(f"SQL: no field configuration for {field_id}")
                    return False
                config_id = int(row[0])
                cur.execute("SELECT customvalue FROM customfieldoption WHERE customfield = %s", (numeric,))
                have = {str(item[0]) for item in cur.fetchall()}
                cur.execute("SELECT COALESCE(MAX(id), 0) FROM customfieldoption")
                next_id = int(cur.fetchone()[0]) + 1
                cur.execute("SELECT COALESCE(MAX(sequence), -1) FROM customfieldoption WHERE customfield = %s", (numeric,))
                sequence = int(cur.fetchone()[0]) + 1
                inserted = 0
                for value in options:
                    if value in have:
                        continue
                    cur.execute(
                        """
                        INSERT INTO customfieldoption
                            (id, customfield, customfieldconfig, parentoptionid, sequence, customvalue, optiontype, disabled)
                        VALUES (%s, %s, %s, NULL, %s, %s, NULL, 'N')
                        """,
                        (next_id, numeric, config_id, sequence, value),
                    )
                    next_id += 1
                    sequence += 1
                    inserted += 1
                cur.execute(
                    """
                    UPDATE sequence_value_item
                    SET seq_id = GREATEST(seq_id, %s)
                    WHERE seq_name = 'CustomFieldOption'
                    """,
                    (next_id + 10,),
                )
                log(f"SQL inserted {inserted} options for {field_id} (Jira cache may need a restart)")
                return True
    except Exception as exc:  # noqa: BLE001
        log(f"SQL option insert failed: {exc}")
        return False


def ensure_options(client: httpx.Client, field_id: str, options: List[str]) -> None:
    if not options:
        return
    if add_options_rest(client, field_id, options):
        return
    log(f"REST options failed for {field_id}; trying admin HTML")
    if add_options_html(field_id, options):
        return
    log(f"HTML options failed for {field_id}; trying database insert")
    add_options_sql(field_id, options)


def user_exists(client: httpx.Client, username: str) -> bool:
    status, _body = api(client, "GET", "/rest/api/2/user", params={"username": username})
    return status < 400


def software_role(client: httpx.Client) -> Dict[str, Any]:
    status, body = api(client, "GET", "/rest/api/2/applicationrole")
    rows = body if isinstance(body, list) else []
    for item in rows:
        if str(item.get("key") or "") == "jira-software":
            return item if isinstance(item, dict) else {}
    return {}


def software_members(client: httpx.Client) -> List[str]:
    status, body = api(
        client,
        "GET",
        "/rest/api/2/group/member",
        params={"groupname": "jira-software-users", "maxResults": 200},
    )
    rows = body.get("values") if isinstance(body, dict) else []
    return [str(item.get("name") or "") for item in rows or [] if item.get("name")]


def remove_user_from_group(client: httpx.Client, username: str, group: str) -> None:
    status, body = api(
        client,
        "DELETE",
        "/rest/api/2/group/user",
        params={"groupname": group, "username": username},
    )
    if status < 400:
        log(f"  removed {username} from {group}")
        return
    log(f"  remove {username} from {group} -> {status} {body}")


def add_user_to_group(client: httpx.Client, username: str, group: str) -> bool:
    status, body = api(
        client,
        "POST",
        "/rest/api/2/group/user",
        params={"groupname": group},
        json={"name": username},
    )
    if status < 400:
        log(f"  {username} → {group}")
        return True
    text = str(body).lower()
    if status in {400, 404} and "already" in text:
        return True
    if "exceed" in text or "licensed" in text or "user tier" in text:
        log(f"  {username} not licensed for Jira Software (seat limit)")
        return False
    log(f"  {username} group {group} -> {status} {body}")
    return False


def license_demo_users(client: httpx.Client) -> None:
    """Timebomb/eval Jira Software is 10 seats. Prefer pentesters, then managers."""
    role = software_role(client)
    remaining = int(role.get("remainingSeats") or 0)
    members = set(software_members(client))
    want = [
        item["username"]
        for item in sorted(DEMO_USERS, key=lambda spec: LICENSE_PRIORITY.get(spec["role"], 9))
        if item["role"] in {"pentester", "manager"}
    ]
    missing = [name for name in want if name not in members]
    if remaining <= 0 and missing:
        demote = [
            item["username"]
            for item in DEMO_USERS
            if item["role"] in {"admin", "user"} and item["username"] in members
        ]
        for name in demote:
            if remaining > 0:
                break
            remove_user_from_group(client, name, "jira-software-users")
            members.discard(name)
            remaining += 1
    for name in missing:
        if remaining <= 0:
            log(f"  {name} exists in Jira but has no Software seat")
            continue
        if add_user_to_group(client, name, "jira-software-users"):
            remaining -= 1
            members.add(name)
    role = software_role(client)
    log(
        f"Jira Software seats: {role.get('userCount')}/{role.get('numberOfSeats')} "
        f"(pentesters/managers licensed first; others can still be assignees)"
    )


def ensure_user(client: httpx.Client, spec: Dict[str, str]) -> bool:
    username = spec["username"]
    if user_exists(client, username):
        log(f"User {username} already exists")
        return True
    status, body = api(
        client,
        "POST",
        "/rest/api/2/user",
        json={
            "name": username,
            "password": DEMO_USER_PASSWORD,
            "emailAddress": spec["email"],
            "displayName": spec["display_name"],
            "notification": False,
        },
    )
    if status < 400:
        log(f"Created user {username} ({spec['role']})")
        return True
    log(f"Could not create {username}: {status} {body}")
    return False


def ensure_demo_users(client: httpx.Client, _project_keys: Sequence[str]) -> List[Dict[str, str]]:
    log(f"Seeding {len(DEMO_USERS)} RAPTOR demo users (from scripts/seed_demo_world.py)")
    created: List[Dict[str, str]] = []
    for spec in DEMO_USERS:
        if spec["username"] == ADMIN_USER:
            continue
        if not ensure_user(client, spec):
            continue
        created.append({"username": spec["username"], "display_name": spec["display_name"], "role": spec["role"]})
    license_demo_users(client)
    return created


def record_demo_users(users: List[Dict[str, str]]) -> None:
    merged_path = os.path.join(OUT_DIR, "credentials.json")
    jira_path = os.path.join(OUT_DIR, "jira.json")
    existing: Dict[str, Any] = {}
    if os.path.exists(merged_path):
        try:
            with open(merged_path, encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, json.JSONDecodeError):
            existing = {}
    jira = existing.get("jira") if isinstance(existing.get("jira"), dict) else {}
    jira["demo_users"] = users
    jira["demo_user_password"] = DEMO_USER_PASSWORD
    existing["jira"] = jira
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(merged_path, "w", encoding="utf-8") as handle:
        json.dump(existing, handle, indent=2)
    if os.path.exists(jira_path):
        try:
            with open(jira_path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            payload = {}
        payload["demo_users"] = users
        payload["demo_user_password"] = DEMO_USER_PASSWORD
        with open(jira_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    log(f"Recorded {len(users)} demo users in {merged_path}")


def seed_users_only() -> int:
    with basic_auth_client() as client:
        wait_rest(client)
        keys = [item["key"] for item in PROJECTS]
        users = ensure_demo_users(client, keys)
        record_demo_users(users)
        log(f"Demo users ready: {len(users)}")
        return 0 if users or DEMO_USERS else 1


def ensure_components_and_versions(client: httpx.Client, project_key: str) -> None:
    status, body = api(client, "GET", "/rest/api/2/project/{0}/components".format(project_key))
    have = {item.get("name") for item in body} if isinstance(body, list) else set()
    for name in COMPONENTS:
        if name in have:
            continue
        api(client, "POST", "/rest/api/2/component", json={"name": name, "project": project_key})
    status, body = api(client, "GET", f"/rest/api/2/project/{project_key}/versions")
    have = {item.get("name") for item in body} if isinstance(body, list) else set()
    for name in VERSIONS:
        if name in have:
            continue
        api(client, "POST", "/rest/api/2/version", json={"name": name, "project": project_key, "released": False})


def issue_types_for(client: httpx.Client, project_key: str) -> List[Dict[str, str]]:
    status, body = api(client, "GET", f"/rest/api/2/issue/createmeta/{project_key}/issuetypes")
    rows = body.get("values") if isinstance(body, dict) else []
    if not rows:
        status, body = api(client, "GET", f"/rest/api/2/project/{project_key}")
        rows = body.get("issueTypes") if isinstance(body, dict) else []
    types = []
    for item in rows or []:
        if not isinstance(item, dict) or item.get("subtask"):
            continue
        ident = str(item.get("id") or "")
        name = str(item.get("name") or "")
        if ident:
            types.append({"id": ident, "name": name})
    return types


def create_pat(client: httpx.Client) -> Optional[str]:
    status, body = api(
        client,
        "POST",
        "/rest/pat/latest/tokens",
        json={"name": "raptor-lab", "expirationDuration": 90},
    )
    if status >= 400:
        status, body = api(client, "POST", "/rest/pat/latest/tokens", json={"name": "raptor-lab"})
    if isinstance(body, dict) and body.get("rawToken"):
        log("Created Jira personal access token")
        return str(body["rawToken"])
    log(f"PAT create failed ({status} {body}); RAPTOR can use username + password as Cloud-style Basic auth")
    return None


def write_credentials(payload: Dict[str, Any]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "jira.json")
    existing = {}
    merged_path = os.path.join(OUT_DIR, "credentials.json")
    if os.path.exists(merged_path):
        try:
            with open(merged_path, encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing["jira"] = payload
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    with open(merged_path, "w", encoding="utf-8") as handle:
        json.dump(existing, handle, indent=2)
    log(f"Wrote {merged_path}")


def main() -> int:
    license_key = load_license()
    log(f"Seeding Jira at {JIRA_URL} (browser URL {PUBLIC_URL})")
    with httpx.Client(base_url=JIRA_URL, timeout=60.0, follow_redirects=True, headers={"User-Agent": "raptor-jira-seed"}) as anon:
        run_setup_wizard(anon, license_key)

    with basic_auth_client() as client:
        wait_rest(client)
        projects = ensure_projects(client)
        vuln_id = ensure_issue_type(client, "Vulnerability", "Security finding reported from RAPTOR.")
        custom = []
        for spec in CUSTOM_FIELDS:
            field = create_custom_field(client, spec)
            field_id = str(field.get("id") or "")
            add_field_to_screens(client, field_id)
            ensure_options(client, field_id, spec["options"])
            custom.append(
                {
                    "id": field_id,
                    "name": spec["name"],
                    "type": spec["type"].rsplit(":", 1)[-1],
                    "options": spec["options"],
                    "in_raptor": False,
                }
            )
        for project in projects:
            ensure_components_and_versions(client, project["key"])
        demo_users = ensure_demo_users(client, [item["key"] for item in projects])
        sec_types = issue_types_for(client, "SEC")
        bug = next((item for item in sec_types if item["name"].lower() == "bug"), sec_types[0] if sec_types else None)
        task = next((item for item in sec_types if item["name"].lower() == "task"), None)
        pat = create_pat(client)
        payload = {
            "browser_url": PUBLIC_URL,
            "docker_url": "http://jira:8080",
            "raptor_base_url": "http://host.docker.internal:8090",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
            "email": ADMIN_EMAIL,
            "auth_type_preferred": "pat" if pat else "api_token",
            "personal_access_token": pat,
            "projects": projects,
            "issue_types": sec_types,
            "vulnerability_issue_type_id": vuln_id,
            "ticket_templates": [
                {
                    "name": "SEC / Bug",
                    "project_key": "SEC",
                    "issue_type": (bug or {}).get("name") or "Bug",
                    "issue_type_id": (bug or {}).get("id"),
                },
                {
                    "name": "SEC / Task",
                    "project_key": "SEC",
                    "issue_type": (task or {}).get("name") or "Task",
                    "issue_type_id": (task or {}).get("id"),
                },
            ],
            "custom_fields_not_in_raptor": custom,
            "extra_system_fields_not_in_raptor": ["components", "fixVersions", "due date", "environment"],
            "demo_users": demo_users,
            "demo_user_password": DEMO_USER_PASSWORD,
            "license_note": "Default timebomb license expires about 3 hours after first apply. Set JIRA_LICENSE to a 30-day evaluation for lasting lab use.",
        }
        write_credentials(payload)
        log("Jira seed complete.")
        return 0


if __name__ == "__main__":
    if "--users-only" in sys.argv:
        sys.exit(seed_users_only())
    sys.exit(main())
