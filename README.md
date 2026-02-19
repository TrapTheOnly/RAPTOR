# RAPTOR Security Platform

RAPTOR (Reconnaissance, Assessment, Penetration Testing, Operations, and Reporting) is a web platform for managing DNS asset inventory and penetration-testing operations in one workflow.

## What the Project Does

- Ingests BIND-style zone files (`*_A_Records`) into a managed asset inventory.
- Tracks record lifecycle and change history.
- Runs role-based pentest workflows (assignment, status, findings, remediation).
- Supports checklist-based testing templates and report templates.
- Generates and stores PDF pentest reports.
- Provides admin tooling for users, permissions, IP source mapping, vulnerability categories, and maintenance operations.

## Architecture

- Frontend: React 19 + MUI 6 (`frontend/`)
- Backend: Flask (`backend/main.py` + `backend/modules/`)
- Database: PostgreSQL (runtime), with one-time SQLite migration support
- Auth: Local admin + local users + LDAP/AD users
- File/report storage: FTP service for uploaded/generated report assets
- Packaging: Multi-stage Docker build with Compose for dev/prod

## Repository Layout

```text
backend/
  main.py                 # Flask app, DB init, routes, periodic zone updates
  modules/                # auth, permissions, pentest/report logic, templates
frontend/
  src/                    # React app (dashboard, records, pentest, admin settings)
Dockerfile                # Builds frontend, packages with backend
Dockerfile.sftp           # SFTP sidecar image
docker-compose.dev.yml    # Development stack
docker-compose.prod.yml   # Production stack
scripts/
  dev.ps1                 # Build frontend -> backend/static, run backend locally
  docker_runner.sh        # Dev helper: rebuild stack and seed sample zone files
```

## Quick Start (Docker)

### 1) Create a root `.env`

Create `RAPTOR_LOCATION\.env` with at least:

```env
# Core app
APP_PORT=5000
SECRET_KEY=replace-with-a-random-secret
ADMIN_USERNAME=awadmin
DATABASE_URL=postgresql://user:password@postgres:5432/raptor
POSTGRES_DB=raptor
POSTGRES_USER=raptor
POSTGRES_PASSWORD=replace-with-a-strong-password

# Storage paths used by backend
DATA_PATH=/appdata/data
BACKUP_FOLDER=/appdata/backups
SHARED_PATH=/usr/app/src/shared

# Zone refresh interval in seconds
UPDATE_TIME=86400

# Session cookie/CORS
CORS_ORIGINS=*
SESSION_COOKIE_SAMESITE=Lax

# LDAP (required for LDAP auth/admin LDAP search)
LDAP_SERVER=ldap.example.com
LDAP_DOMAIN=example.com
LDAP_USER=svc_account@example.com
LDAP_PASS=replace-me

# FTP (used by pentest report/image storage)
FTP_USER=raptor_ftp_user
FTP_PASS=replace-me

# TLS (needed when APP_PORT=5000 mode is used)
CERT_FILE=/certs/cert.pem
KEY_FILE=/certs/key.pem

# Optional hardening knobs
FAILED_LOGIN_ATTEMPT_LIMIT=5
LOGIN_LOCKOUT_BASE_MINUTES=1
LOGIN_LOCKOUT_MAX_MINUTES=0
```

### 2) Start the dev stack

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Default dev access:

- URL: `http://localhost:1337`
- App container port mapping: `1337 -> APP_PORT` (commonly `5000`)
- SFTP sidecar: `localhost:2222`

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

## Production Compose

Use:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` maps host `1337` to container `5000` and expects TLS cert/key paths when running in HTTPS mode.

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

- Backend scans `SHARED_PATH` for files named `*_A_Records`.
- It parses BIND A-record entries, updates current records, and keeps backups under `BACKUP_FOLDER`.
- Periodic update interval is controlled by `UPDATE_TIME` (seconds).
- Admins can trigger an immediate refresh via `POST /manual-update`.

## Security and Access Control

- Role defaults: `user`, `pentester`, `manager`, `admin`.
- Optional per-user extra permissions are constrained by role policy.
- Session controls include idle timeout, extension window, and max active lifetime.
- Login lockout policy is configurable through env vars.
- Admin account enforces password-reset flow for bootstrap credentials.

## API Surface (High-Level)

Authentication/session:

- `POST /login`
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

## Operations and Troubleshooting

- App logs: `DATA_PATH/application.log`
- Runtime database: PostgreSQL (`DATABASE_URL`)
- Legacy migration source (optional): `DATA_PATH/database.db`
- Zone-file backups: `BACKUP_FOLDER/<domain>/...`
- If no assets appear, verify `SHARED_PATH` contains valid `*_A_Records` files and run `POST /manual-update`.

## Current Focus Areas

- Documentation and onboarding polish
- Continued hardening of auth/session policies
- UX refinements in records and pentest workflows
