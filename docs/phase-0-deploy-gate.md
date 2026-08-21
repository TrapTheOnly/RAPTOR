# Phase 0 — Deploy gate

Engineering spec for RAPTOR’s production-hardening and data-model foundation. This is not an in-app docs portal article.

**Status:** implemented, pending production deploy  
**Non-goals:** BIND collector agent, Cloudflare / Route 53 / Alibaba connectors, FTP replacement, engagements / retest UX, extra scanner models.

## Goal

Make RAPTOR safe to run and safe to ingest into. Design the collector (Phase 1) against this foundation; do not deploy a second DNS source until this gate is green.

## Current state

- HTTP: `app.run(..., debug=True)` in `backend/main.py`. Init runs only when `WERKZEUG_RUN_MAIN=true`.
- Compose sets `ENVIRONMENT=development`; Python never reads it. Logs are DEBUG and truncate on start (`FileHandler` mode `w`).
- Kali `POST /api/command` has no auth and uses `shell=True`.
- Ingest is collector POST + cloud DNS pulls. Automated names missing from every enabled source’s latest A batch become `missing`.
- Findings are JSON on `pentest_data.vulnerabilities`. Dashboard dumps that blob. Pentest list includes `notes`.
- Service API keys are stored plaintext. MCP is published on the host.

**Trap:** turning Flask `debug` off without WSGI stops ingest, because init is gated on the Werkzeug reloader env.

## Target

Web traffic runs under gunicorn (`-w 2`). DNS sync runs in a second gunicorn process (`RAPTOR_ROLE=worker`, `-w 1`) with a job loop thread. Kali requires `KALI_INTERNAL_TOKEN`. Destructive tools are an Admin Settings switch. Inventory uses `dns_sources` + `dns_observations` with per-source missing. Findings live in `pentest_findings`. API keys are hash-only. Prod does not publish the MCP port.

## Workstreams

1. Gunicorn runtime, `ENVIRONMENT`, `/healthz`, append logs, fail-closed `SECRET_KEY` / CORS in production.
2. Kali token auth. Admin toggle `allow_destructive_tools` on `scanner_config`. Safe default tool allowlist.
3. `dns_sources` + `dns_observations`. Source-scoped missing. UNIQUE `records.name`.
4. `pentest_findings` dual-write. Scanner findings are `draft`. Strip notes and finding bodies from list APIs. Paginate service-api lists.
5. Gunicorn worker for `dns_sync` jobs. Hash-only API keys. Unpublish MCP in prod. `audit_events`.

## Deploy notes

Production compose now requires `ENVIRONMENT=production`, an explicit `CORS_ORIGINS` allowlist, and a non-default `SECRET_KEY`. Set `KALI_INTERNAL_TOKEN` before starting Kali or the scanner. DNS sync runs in the `worker` service (`RAPTOR_ROLE=worker`). The MCP port is not published on the host in production.

A collector should POST normalized RR batches to an ingest API with `source_id` + cursor. Do not invent another `*_A_Records` filename contract. Phase 1 implements that API at `POST /collector/v1/ingest`; see `docs/phase-1-collector.md`.
