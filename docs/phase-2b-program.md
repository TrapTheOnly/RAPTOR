# Phase 2b — Waves, presets, env ACL, zones, share, signed exports

Engineering spec. Depends on Phase 2a (`0014`–`0016`). SLA clocks and assignment email stay parked. Cloud DNS is Phase 3.

**Status:** implemented  
**Schema:** `0017_phase2b.py`

## Goal

Give the app program a wave object, named export presets on the **same** confirmation sheet, contractor env ACL, env-scoped checklists, a DNS suffix catalog, cross-app attach of shared infra, HMAC-signed frozen PDFs, and wire `environments.allow_destructive` as the scanner job ceiling.

## Frozen rules

- Waves are N:1 application, optional env set, host snapshot at kickoff. Close does **not** delete findings or `report_exports`. Notebook reset remains a separate button.
- Four named packages are **presets on one sheet**, not four PDF products: `owner_delivery`, `wave_archive`, `retest_pack`, `internal_draft`.
- Env ACL: empty ACL = open to anyone with pentest view. Non-empty ACL = those usernames plus `app_lead` plus admin/manager overrides.
- Shared infra: owning app keeps the notebook. Consumer apps may attach the host as an occurrence only after an explicit share.
- Signed PDF: HMAC-SHA256 of `content_hash` with `SECRET_KEY`. Not a public CA / PAdES product.
- Scanner: global `allow_destructive_tools` AND env `allow_destructive`. Concurrent jobs for hosts in that env cannot exceed `environments.max_concurrent_scans` (default 1).

## Schema

`engagement_waves(id, application_id, name, status open|closed, env_ids JSON, host_snapshot JSON, opened_by, opened_at, closed_at, notes)`

`environment_acl(environment_id, username)` UNIQUE

`environment_checklists(environment_id, template_key)` UNIQUE

`dns_zones(id, suffix UNIQUE, display_name, application_id NULL, notes)`

`shared_host_apps(record_id, consumer_application_id)` UNIQUE — owner is still `records.application_id`

`environments.max_concurrent_scans INTEGER NOT NULL DEFAULT 1`

`report_exports.signature`, `report_exports.wave_id`

## Packages

| Key | Sheet defaults |
|-----|----------------|
| owner_delivery | prod checked; drafts off |
| wave_archive | wave env_ids; drafts off; wave_id stored |
| retest_pack | selected envs; only open/retest occurrences |
| internal_draft | selected envs; drafts allowed |

## APIs

| Method | Path | Notes |
|--------|------|--------|
| GET/POST | `/api/apps/<id>/waves` | Open wave snapshots in-scope hosts. |
| POST | `/api/apps/<id>/waves/<id>/close` | Status `closed`. Never deletes findings or exports. |
| GET/PUT | `/api/apps/<id>/environments/<id>/acl` | Empty list = open. Non-empty = listed users + app_lead + admin/manager. |
| GET/PUT | `/api/apps/<id>/environments/<id>/checklists` | `{ template_keys }`. Merged into host `checklist_states` on notebook load. |
| GET/POST | `/api/dns-zones` | Optional `application_id`. Suffix catalog for the export sheet. |
| DELETE | `/api/dns-zones/<id>` | Catalog row only. |
| POST | `/api/apps/<id>/hosts/<record_id>/share` | `{ consumer_application_id }`. Owner keeps the notebook. |
| GET | `/api/apps/<id>/shared-hosts` | Hosts shared *to* this app (occurrence attach only). |
| PATCH | `/api/findings/<id>/occurrences/<record_id>` | `{ status }`. Rolls the finding's global status and the host rollup forward. |
| POST | `/api/apps/<id>/occurrences/bulk-status` | `{ to_status, from_statuses?, env_ids?, record_ids? }`. Defaults open-like → `retest`. |
| POST | `/api/apps/<id>/generate-report` | Same sheet. Body `package` + optional `wave_id`. HMAC on freeze. |
| GET | `/api/report-exports/<id>/verify` | HMAC-SHA256 of `content_hash` with `SECRET_KEY`. |

Occurrence status is the unit of remediation truth: `open | draft | retest` are open-like, `fixed | not_affected | accepted` are closed. The finding's stored status stays global and is recomputed on every occurrence write, so `retest_pack` selects real work rather than a static filter.

PUT environment accepts `allow_destructive` and `max_concurrent_scans` (1–10, default 1). Scanner launch ANDs global `allow_destructive_tools` with the env flag and caps concurrent jobs per env.

## Interface

Shared primitives live in `frontend/src/components/program/`: `PageHeader`, `StatCardGrid`, `SectionCard`, `EmptyState`, `StatusChip`/`SeverityChip`, `EnvChip`, and `tokens.js` (severity tiers, status colours, environment accents, package definitions). They mirror the Dashboard KPI language and the Records card language so the pentest area reads as part of the same product.

| Surface | Route | Shape |
|---------|-------|-------|
| Application index | `/pentest` | KPI strip, name filter + host typeahead + sort + "needs attention", app cards with coverage bars |
| App workspace | `/apps/<id>` | Breadcrumb header, KPI strip, tabs: Overview, Findings, Hosts, Environments, Waves, Program |
| Environment drill-down | `/apps/<id>/envs/<envId>` | Same shell; Environments tab becomes Environment settings |
| Host notebook | `/pentest/record/<id>` | Blast-radius panel per finding with env chips and per-occurrence status |

Findings render as severity-bordered cards that expand into their occurrence list; each occurrence row carries its environment, host state, and a status control wired to the occurrence PATCH. Merge and ticket editing are dialogs — the workspace uses no `window.prompt`. The export sheet debounces a `preview: true` call and shows finding count, watermark, excluded drafts, and excluded unassigned hosts before anything is frozen, then reports HMAC verification after generating.

## Out of this slice

SLA/email product, Cloudflare/Route 53/Alibaba, PAdES certificates.
