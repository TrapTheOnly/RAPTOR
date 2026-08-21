# RAPTOR Security Platform

RAPTOR (Reconnaissance, Assessment, Penetration Testing, Operations, and Reporting) is a web platform for managing DNS asset inventory and penetration-testing operations in one workflow.

## What the Project Does

- Ingests DNS from collector agents that parse zone files locally and POST normalized RR batches, and from cloud DNS pull connectors.
- Tracks record lifecycle and change history.
- Runs role-based pentest workflows (assignment, status, findings, remediation).
- Supports checklist-based testing templates and report templates.
- Generates and stores PDF pentest reports.
- Provides admin tooling for users, permissions, IP source mapping, vulnerability categories, and maintenance operations.

## Architecture

- Frontend: React 19 + MUI 6 (`frontend/`)
- Backend: Flask (`backend/main.py` + `backend/modules/`)
- Database: PostgreSQL (runtime), with one-time SQLite migration support
- Auth: RAPTOR login form; Keycloak stores users, roles, LDAP federation, and service-account clients
- File/report storage: FTP service for uploaded/generated report assets
- MCP integration service: standalone Python MCP server (`mcp/`) over streamable HTTP
- AI scanner: optional sidecar (`scanner/`) plus Kali and a local-llm manager for the bundled Qwen GGUF
- DNS collector agent: standalone Python agent (`collector/`) that enrolls and POSTs RR batches
- Packaging: Multi-stage Docker build with Compose for dev/prod

## Repository Layout

```text
backend/
  main.py                 # Flask app, DB init, routes
  modules/                # auth, permissions, pentest/report logic, templates
frontend/
  src/                    # React app (dashboard, records, pentest, admin settings)
collector/
  cmd/raptor-collector/   # Packaged Go agent (Linux/Windows binaries served by RAPTOR)
Dockerfile                # Builds frontend, packages with backend
Dockerfile.collector      # Collector agent image
docker-compose.dev.yml    # Development stack
docker-compose.prod.yml   # Production stack
scripts/
  dev.ps1                 # Build frontend -> backend/static, run backend locally
  docker_runner.sh        # Guided installer: .env, secrets, Compose up
```

## Quick Start (Docker)

The installer writes `.env`, generates secrets, and starts Compose. Run it from the repo root:

```bash
./scripts/docker_runner.sh
```

It asks for deploy mode (dev or prod), core secrets, CORS, FTP, optional LDAP, and whether to start Kali + the AI scanner + local model runtime. Re-runs keep existing `.env` values unless you replace them. LLM API keys are configured in Admin Settings, not required at install time.

Non-interactive examples:

```bash
./scripts/docker_runner.sh --dev --yes --build --no-scanner
./scripts/docker_runner.sh --prod --yes --build   # requires CORS_ORIGINS in .env
./scripts/docker_runner.sh --help
```

### 1) `.env` (created by the installer)

The wizard writes a root `.env`. You can also create one yourself with at least:

```env
# Core app
APP_PORT=5000
APP_USE_TLS=false
SECRET_KEY=replace-with-a-random-secret
ADMIN_USERNAME=awadmin
DATABASE_URL=postgresql://user:password@postgres:5432/raptor
POSTGRES_DB=raptor
POSTGRES_USER=raptor
POSTGRES_PASSWORD=replace-with-a-strong-password

# Storage paths used by backend
DATA_PATH=/appdata/data

# Optional: pin persistent Docker volume names explicitly.
# Set these when migrating from an older Compose project name so existing data
# keeps mounting after a rename like web-application-monitoring-software -> raptor.
DB_AND_BACKUPS_VOLUME_NAME=raptor_db_and_backups_volume
CERTS_VOLUME_NAME=raptor_certs_volume
FTP_VOLUME_NAME=raptor_ftp_volume
POSTGRES_DATA_VOLUME_NAME=raptor_postgres_data_volume
LLM_MODELS_VOLUME_NAME=raptor_llm_models_volume

# Session cookie/CORS
CORS_ORIGINS=*
SESSION_COOKIE_SAMESITE=Lax

# MCP service (standalone container)
MCP_SERVER_TOKEN=replace-with-a-random-mcp-bearer-token
RAPTOR_SERVICE_API_KEY=replace-with-a-service-account-api-key

# AI Scanner service
SCANNER_INTERNAL_TOKEN=replace-with-a-random-scanner-internal-token
LOCAL_LLM_BASE_URL=http://local-llm:8083
# Optional Bedrock env fallback if a Bedrock connection has no token in Settings
AWS_BEARER_TOKEN_BEDROCK=
AWS_REGION=us-east-1
# GGUF weights (~17.6 GB) download into llm_models when you Install RAPTOR Local in Settings.
# GPU: if the host has NVIDIA and Docker can see /dev/nvidia0, llama-server offloads layers.
# CPU-only is allowed and labeled slow. Weights are never baked into the image.
RAPTOR_API_BASE_URL=http://app:5000
MCP_PORT=8081
RAPTOR_API_TIMEOUT_SECONDS=30
MCP_ALLOWED_HOSTS=raptor.azercell.com,raptor.azercell.com:443
MCP_ALLOWED_ORIGINS=https://raptor.azercell.com

KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_PUBLIC_URL=http://localhost:8180
RAPTOR_PUBLIC_URL=http://localhost:1337
KEYCLOAK_REALM=raptor
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=replace-me
KEYCLOAK_LOGIN_CLIENT_SECRET=replace-with-a-random-login-client-secret
KEYCLOAK_BACKEND_CLIENT_SECRET=replace-with-a-random-backend-client-secret

# LDAP (optional; Keycloak user federation + Settings allowlist)
LDAP_SERVER=ldap.example.com
LDAP_DOMAIN=example.com
LDAP_USER=svc_account@example.com
LDAP_PASS=replace-me
# Optional LDAP knobs (blank is fine)
# LDAP_USERS_DN=OU=Users,DC=example,DC=com
# LDAP_VENDOR=ad
# LDAP_USE_SSL=false
# LDAP_START_TLS=false
# LDAP_TRUSTSTORE=never
# LDAP_USERNAME_ATTR=sAMAccountName

# Optional OIDC/SAML broker (users must still receive raptor-access in Settings)
# Prefer Settings -> User Management -> Sign-in / SSO. Env vars only seed a provider
# when that alias does not already exist. RAPTOR login stays a branded form; enabled
# OIDC/SAML connections appear as Sign in with … buttons (authorization code + kc_idp_hint).
# Broker-only users must be allowlisted (including before first SSO) in Settings.
# KEYCLOAK_IDP_ALIAS=corp-oidc
# KEYCLOAK_IDP_PROVIDER=oidc
# KEYCLOAK_IDP_DISPLAY_NAME=Corporate SSO
# KEYCLOAK_IDP_CLIENT_ID=
# KEYCLOAK_IDP_CLIENT_SECRET=
# KEYCLOAK_IDP_ISSUER=https://idp.example.com/realms/corp

# FTP (used by pentest report/image storage)
FTP_USER=raptor_ftp_user
FTP_PASS=replace-me

# TLS (only needed when APP_USE_TLS=true)
CERT_FILE=/certs/cert.pem
KEY_FILE=/certs/key.pem

# Optional hardening knobs
# Login brute-force is enforced by Keycloak (5 failures, exponential wait).
```

### 2) Start the stack

Prefer `./scripts/docker_runner.sh`. To start Compose yourself after `.env` exists:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Default dev access:

- URL: `http://localhost:1337`
- App container port mapping: `1337 -> APP_PORT` (commonly `5000`)

### 2.1) One-time SQLite -> PostgreSQL data migration

Automatic migration is disabled in Compose/CI.  
For legacy deployments that still have a SQLite database, run:

```bash
DATABASE_URL=postgresql://user:password@postgres:5432/raptor \
POSTGRES_DB=raptor \
POSTGRES_USER=raptor \
POSTGRES_PASSWORD=replace-with-a-strong-password \
./scripts/manual_migrate_to_postgres.sh docker-compose.prod.yml
```

The script runs both migration and verification once, then prints the restart command.
Runtime remains PostgreSQL-only. If `DATABASE_URL` is missing, the backend exits at startup.

### 3) Initial admin credentials

On first startup, the backend creates the admin account and writes credentials to:

- `DATA_PATH/initial_admin_credentials.txt`

Delete this file after first successful admin login.

## Standalone MCP Service

RAPTOR includes a separate MCP service container that does not run inside the main backend runtime.

- MCP transport: streamable HTTP
- MCP endpoint: `http://localhost:8081/mcp`
- Health endpoint: `http://localhost:8081/healthz`
- MCP tools (v1): `list_records`, `list_pentests`

The MCP service authenticates inbound clients with `Authorization: Bearer <MCP_SERVER_TOKEN>` and authenticates to RAPTOR via `X-API-Key: <RAPTOR_SERVICE_API_KEY>`.

If MCP is published behind the main domain through a WAF or reverse proxy, set `MCP_ALLOWED_HOSTS` to the public host values the proxy forwards in the `Host` header. For a standard HTTPS publish on the main domain, use values like `raptor.azercell.com,raptor.azercell.com:443`. Set `MCP_ALLOWED_ORIGINS` if browser-based clients will send an `Origin` header.

Verify service health:

```bash
curl http://localhost:${MCP_PORT:-8081}/healthz
```

Client connection pattern (Python MCP SDK):

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    headers = {"Authorization": "Bearer <MCP_SERVER_TOKEN>"}
    async with streamablehttp_client("http://localhost:8081/mcp", headers=headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])  # ['list_records', 'list_pentests']

asyncio.run(main())
```

## Production Compose

Prefer:

```bash
./scripts/docker_runner.sh --prod --build
```

Or, with `.env` already valid:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` maps host `1337` to container `5000`. TLS is optional and controlled by `APP_USE_TLS` (`false` by default).

Persistent volumes are now pinned by explicit Docker volume names. For existing installations that were previously deployed under another Compose project name, set the `*_VOLUME_NAME` variables in `.env` to the old Docker volume names before the first deploy after migration. Example:

```env
POSTGRES_DATA_VOLUME_NAME=web-application-monitoring-software_postgres_data_volume
```

## Local Development (Without Docker)

### Option A: Integrated local run (recommended in this repo)

```powershell
cd RAPTOR_LOCATION
.\scripts\dev.ps1 -Install
```

Prerequisite (first time only): create `backend/env` and install backend dependencies once.

```powershell
cd RAPTOR_LOCATION\backend
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
```

Then run `.\scripts\dev.ps1 -Install`. The script installs/builds frontend, copies build output into `backend/static`, activates `backend/env`, then starts `python main.py`.
Set `DATABASE_URL` in your environment before running backend locally.

### Option B: Manual split workflow

Backend:

```powershell
cd RAPTOR_LOCATION\backend
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
python main.py
```

Set `DATABASE_URL` (and related Postgres credentials) in your shell or `.env` first.

Frontend-only dev server (UI work):

```powershell
cd RAPTOR_LOCATION\frontend
npm install
npm start
```

Note: the frontend uses relative API paths (for same-origin deployment). If you run `npm start` separately, configure proxy/CORS accordingly.

## Data Ingestion Model

- Collector agents parse BIND, PowerDNS, or Windows DNS locally and POST RR batches to `POST /collector/v1/ingest`.
- Cloud DNS connectors (Cloudflare, Route 53, AliDNS, Azure, GCP) pull on the worker.
- Admins can trigger collectors and cloud sync via `POST /admin/domains/refresh`.

## Security and Access Control

- Role defaults: `user`, `pentester`, `manager`, `admin`.
- Optional per-user extra permissions are constrained by role policy.
- Session controls include idle timeout, extension window, and max active lifetime.
- Login brute-force protection is handled by Keycloak (allowlist role `raptor-access` is still required).
- Admin account enforces password-reset flow for bootstrap credentials. The Keycloak console is not the supported admin UI.

## API Surface (High-Level)

Authentication/session:

- `POST /login`
- `GET /auth/sso/providers`
- `GET /auth/sso/{alias}/start`
- `GET /auth/sso/callback`
- `GET /session-status`
- `POST /session/extend`
- `POST /logout`

Records/apps:

- `GET /api/records`
- `POST /api/records/{id}`
- `DELETE /api/records/{id}`
- `GET|POST /api/apps`
- `PUT|DELETE /api/apps/{id}`

Pentest and reporting:

- `GET /pentest/records`
- `POST|DELETE /pentest/{record_id}`
- `GET|DELETE /pentest/{record_id}/report`
- `POST /pentest/{record_id}/generate-report`
- `GET|DELETE /pentest/{record_id}/generated-report`
- `POST /pentest/{record_id}/images`
- `GET /pentest/images/{filename}`

Service API datasets:

- `GET /service-api/v1/records`
- `GET /service-api/v1/pentests`

Admin and taxonomy:

- `GET /ldap-search`
- `POST /add-user`
- `POST /add-local-user`
- `GET /existing-users`
- `POST /update-user-role`
- `POST /update-user-permissions`
- `DELETE /delete-user`
- `GET|POST|DELETE /ip-sources`
- `GET|POST|DELETE /vuln-categories`
- `GET|POST|PUT|DELETE /checklist-templates`
- `GET|POST|PUT|DELETE /report-templates`

MCP service:

- `GET /healthz` (MCP container)
- `POST/GET /mcp` (streamable HTTP MCP protocol endpoint)

## Operations and Troubleshooting

- App logs: `DATA_PATH/application.log`
- Runtime database: PostgreSQL (`DATABASE_URL`)
- Legacy migration source (optional): `DATA_PATH/database.db`
- If no assets appear, enroll a collector or add a cloud DNS connector and run `POST /admin/domains/refresh`.

MCP token/key rotation runbook:

1. Rotate RAPTOR service account API key in Admin Settings.
2. Update `RAPTOR_SERVICE_API_KEY` secret for MCP deployment.
3. Restart MCP container.
4. Rotate `MCP_SERVER_TOKEN` secret.
5. Restart MCP container and update AI client bearer token.

## Third-party notices

Brand marks in Admin Settings, records, and the AI scanner UI come from
[`@lobehub/icons`](https://github.com/lobehub/lobe-icons) (MIT). The full notice
and the icon mapping are in [`copyright.md`](copyright.md).

## Current Focus Areas

- Phase 0 deploy gate: see `docs/phase-0-deploy-gate.md`
- Phase 1 collector agent: see `docs/phase-1-collector.md`
- Phase 2a app program (apps, environments, multi-host findings): see `docs/phase-2-app-program.md`
- Phase 2b waves, export presets, env ACL, zones, shared infra, signed PDFs: see `docs/phase-2b-program.md`
- Phase 3 cloud DNS connectors (Cloudflare, Route 53, Alibaba, Azure, GCP): see `docs/phase-3-cloud-dns.md`
- Documentation and onboarding polish
- Continued hardening of auth/session policies
- UX refinements in records and pentest workflows
