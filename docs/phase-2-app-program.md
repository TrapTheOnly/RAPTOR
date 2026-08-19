# Phase 2a — App program

Engineering spec for RAPTOR’s application / environment / multi-host finding model. This is not an in-app docs portal article.

**Status:** implemented  
**Depends on:** Phase 0 `pentest_findings` + UNIQUE `records.name`; Phase 1 collector (ingest still leaves `application_id` NULL). Schema migrations are `0014_environments`, `0015_finding_occurrences`, `0016_report_exports` (collector already occupies `0013`).  
**Non-goals (2b):** engagements/waves, four named export packages, env-scoped contractor ACL, env checklists, DNS zone catalog, cross-app shared-infra M:N, SLA/email product, signed PDFs, per-env scanner job UI, cloud DNS connectors.

## Goal

Pentest Google as one application with prod / staging / preprod / QA environments. Write a CORS or cookie-domain finding once. Export an Owner-delivery PDF that defaults to production. Stop deleting findings on the annual reset.

Phase 1 collector ingest is unchanged: new `records` columns are nullable or defaulted, so `store_records_in_db` INSERT lists stay as they are.

## Frozen rules

- One application. Environments are children (`prod`, `stg`, `pp`, `qa`, `unassigned`). Never “Google QA” as a second app.
- One FQDN = one `records` row = at most one env. Global UNIQUE `name` stays. Unfiled hosts (no app) have `environment_id` NULL.
- App page is the pentest workspace. Env is a deep-link drill-down. Host page is the leaf (ports, notes, nmap).
- `pentest_findings.record_id` stays NOT NULL as **found-here**. Blast radius is `finding_occurrences`. Found-here is always an occurrence row.
- Stored finding status is **global** (open until every non-draft occurrence is `fixed` or `not_affected`). Packs may badge “fixed in this pack.”
- One export sheet. 2a package is Owner delivery, which **defaults to prod** even from the app page. `include_in_exec_report` only pre-checks the env checkbox.
- Host export is called “host.” Suffix/prefix filter on the sheet is v1 domain export.
- Annual reset must not `DELETE` `pentest_data`, `pentest_findings`, or `report_exports`.
- `in_scope` backfill ignores empty auto-created pentest notebooks. True only if status is In Progress / Completed, or a human finding exists.
- Shared SSO stays on the owning app. Consumer apps cannot attach that host in v1.

## Schema

`environments` — UNIQUE `(application_id, slug)`. Seed per app: `unassigned`, `prod`, `stg`, `pp`, `qa`. `prod.is_production` and `include_in_exec_report` are true; others false.

`records.environment_id` nullable FK. `records.in_scope` default false. `records.env_suggestion` optional heuristic, never auto-committed. `application_id` is a maintained cache of `environments.application_id`.

`applications` thickens: `owner`, `data_class`, `roe_link`, `cookie_domain`, `idp`, `token_audience`, `app_lead` (metadata, not ACL).

`pentest_findings` adds `title`, `auth_context`, `ticket_url`, `application_id`. Status: `draft | open | fixed | accepted | not_affected`.

`finding_occurrences(finding_id, record_id, status, primary_url, severity_override, evidence_note)` UNIQUE `(finding_id, record_id)`.

`report_exports` — immutable snapshot rows (`scope_kind` application | environment | host). Re-export inserts a new row. Host `pentest_data.generated_report_*` remains the host convenience path and is copied into `report_exports` on generate.

## APIs

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/apps` | Apps with env coverage. Used as pentest index. |
| GET/PUT | `/api/apps/<id>` | Thick metadata. |
| GET/POST | `/api/apps/<id>/environments` | Per-app catalog. POST creates extra slugs. |
| DELETE | `/api/apps/<id>/environments/<id>` | Blocked for `unassigned` or in-use envs. Unused seeded slugs (`prod`, `stg`, `pp`, `qa`) can be removed and are not re-seeded. |
| GET | `/api/hosts/search` | Paginated host typeahead for the app index. |
| PUT | `/api/apps/<id>/environments/<id>` | RoE fields. |
| POST | `/api/apps/<id>/hosts/assign` | `{ record_ids, environment_id, in_scope? }` |
| GET | `/api/apps/<id>/hosts` | Paginated. `q`, `env_id`, `in_scope`, `limit`, `offset`. |
| GET/POST | `/api/apps/<id>/findings` | Paginated inbox. POST creates with found-here + occurrences. |
| PATCH | `/api/findings/<id>` | Narrative / CVSS / ticket. |
| POST | `/api/findings/<id>/occurrences` | Attach hosts in this app. |
| POST | `/api/findings/<id>/merge` | Union occurrences. Survivor keeps CVSS and ticket. |
| POST | `/api/findings/<id>/promote` | Scanner draft → open on this host. Optional `candidate_record_ids`. |
| POST | `/api/apps/<id>/generate-report` | Confirmation sheet body. Owner delivery defaults prod. |
| GET | `/api/report-exports/<id>` | Download frozen PDF. |
| POST | `/pentest/reset-keep-open` | Notebook-only reset. Never deletes findings. |

Pagination: `limit`/`offset`, max 200.

## Export sheet

Owner delivery defaults: prod env checked; drafts hard-off; notes/creds omitted; Unassigned listed but not included as prod line items; QA-only findings excluded; sibling-env occurrences of a prod finding render as Also observed.

`include_in_exec_report` pre-checks the env box. Watermark is derived (`PRODUCTION` / `NON-PROD`). Live query is preview; Generate persists `report_exports`.

## Reset

Phrase: `RESET NOTEBOOKS KEEP FINDINGS`. Clears host pentest `status` to Not Started and checklist/notes/ports on selected (or all) notebooks. Findings, occurrences, and `report_exports` stay.

## Phase 1 compatibility

Collector `INSERT INTO records (name, ip_address, source, ...)` does not mention `environment_id` / `in_scope`. Those columns default. New automated names remain unfiled until a human assigns an app/env.

## Interface

The app index, workspace, environment drill-down, export sheet, and the notebook's blast-radius panel are described in `docs/phase-2b-program.md` under Interface. Shared UI primitives live in `frontend/src/components/program/`.

## 2b

Waves, named sheet presets, env ACL, env checklist, zone catalog, cross-app attach, signed PDF, per-env scanner job ceiling wiring.
