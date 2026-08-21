# Phase 3 — Cloud DNS connectors

Engineering spec for RAPTOR’s Cloudflare, Route 53, Alibaba Cloud DNS, Azure DNS, and Google Cloud DNS pull connectors. This is not an in-app docs portal article.

**Status:** implemented  
**Depends on:** Phase 0 `dns_sources` / `dns_observations` / UNIQUE `records.name`; Phase 1 `apply_ingest_batch`; Phase 2 unfiled automated hosts. Schema migration is `0022_cloud_dns.py`.  
**Non-goals (Phase 4+):** AAAA / CNAME-to-A / TXT / MX host projection, dangling-CNAME findings, certificates, HTTP probes, auto-creating apps from hosted-zone names, SLA/email, PAdES, FTP replacement.

## Goal

Pull public DNS from Cloudflare, Amazon Route 53, Alibaba Cloud DNS, Azure DNS, and Google Cloud DNS into the same ingest pipeline the BIND collector already uses. One FQDN stays one pentest host. Cloud names land unfiled. Testers assign them to applications with the Phase 2 assign API.

## Frozen rules

- Pull connectors, not agents. Do not clone `store_records_in_db` per provider.
- One `dns_sources` row per **account/token**, not per zone. Provider zone id and record id live on the observation.
- Same projection as Phase 1: all RRs → `dns_observations`; only A with a real IPv4 → `records`. MX/TXT/NS/CNAME/AAAA/ALIAS stay facts until Phase 4.
- New cloud names are unfiled (`environment_id` NULL, `in_scope` false). No auto-assign to an app from zone name. No auto-promote Unassigned → Prod.
- One FQDN, one `records` row. Multi-source A disagreement is a conflict, not a second host and not last-write-wins.
- A name is `missing` only if **no enabled source’s latest A batch** still contains it.
- Provider tokens are Fernet-encrypted at rest. GET never returns secrets.
- Phase 2b `dns_zones` remains the export suffix catalog. Cloud hosted zones are not that table.
- `ip_sources` is the `records.source` label. Cloud pull ingest creates (or updates) a provider group — Cloudflare, AWS, Azure, Google Cloud, or Alibaba Cloud — and adds the A-record IPs from that connector. Collector ingest still uses existing mappings (Corp/DMZ/Other). DNS provider identity also lives on `dns_sources.type`.
- Collectors stay push (`bind_agent`). The worker never pulls them.
- Domain refresh runs collectors + enabled cloud pulls. There is no RAPTOR-side zone-file drop-folder.

## Schema

Migration `0022_cloud_dns.py`:

- `dns_observations.provider_zone_id` TEXT
- `dns_observations.provider_record_id` TEXT
- `dns_observations.zone` TEXT
- Index `(source_id, batch_id)`

`dns_sources.type` values used in this slice: `bind_agent`, `cloudflare`, `route53`, `alidns`, `azure`, `gcp`. Legacy `bind_file` rows are disabled by migration `0026_disable_bind_file.py`.

`dns_sources.config` is JSON. Secret fields (`api_token`, `aws_secret_access_key`, `access_key_secret`, `client_secret`, `service_account_json`, `private_key`) are Fernet-encrypted with a key derived from `SECRET_KEY`. Optional non-secrets: `zone_allowlist`, `zone_denylist`, `interval_seconds`, AWS `access_key_id` / `region` / `role_arn`, Aliyun `access_key_id`, Azure `tenant_id` / `client_id` / `subscription_id`, GCP `project_id` / `client_email`.

## Ingest

Cloud adapters implement `DnsConnector` (`list_zones`, `fetch_records`) and normalize to Phase 1 `ResourceRecord`s. The worker (or sync-now) calls `apply_ingest_batch(source_id, records, cursor=…)`.

Live-set missing: union of A FQDNs in each enabled source’s latest batch, plus the current batch. Automated hosts previously seen as A by this source and absent from that live set become `missing`. BIND dropping a name Cloudflare still serves must not tombstone the host.

Multi-source A conflict: if an existing automated host’s IP differs from this source’s A, keep the current pentest IP, set `sync_conflict` with reason `multi_source_a_disagreement`, and notify admins. Resolver POST accepts `{ ip_address }` or `{ source_id }`. Manual-vs-import conflicts keep the existing “adopt live import” path.

Round-robin A from **one** source: first address still wins.

## Adapters

| Type | Client | Auth | Notes |
|------|--------|------|-------|
| `cloudflare` | `httpx` `api.cloudflare.com/client/v4` | API token (Zone.DNS Read + Zone.Zone Read) | Proxied A records project (anycast is public surface). |
| `route53` | `boto3` | access key + secret, optional region / assume-role | Alias records are observed as `ALIAS` and are not projected unless rdata is IPv4. |
| `alidns` | `httpx` Aliyun RPC `alidns.aliyuncs.com` | AccessKey id + secret | CNAME stored, not projected. |
| `azure` | `httpx` ARM `management.azure.com` 2018-05-01 | Entra app: tenant, client id, client secret, subscription | Private DNS zones skipped. Alias `targetResource` observed as `ALIAS`. |
| `gcp` | `httpx` `dns.googleapis.com/dns/v1` | Service account JSON (JWT → oauth2.googleapis.com) | Private managed zones skipped. `rrdatas` already BIND-shaped. |

Cloud default interval is 3600 seconds. Optional `config.zone_allowlist` / `zone_denylist` match zone name or provider zone id.

### Live API notes (matched to vendor docs)

- **Cloudflare:** `Authorization: Bearer`. List Zones `per_page` max is **50** (`status=active`). DNS records use `per_page=1000` (API max is much higher). MX rdata is `"{priority} {content}"`. Optional `config.account_id` is sent as `account.id`.
- **Route 53:** `ListHostedZones` MaxItems 100; `ListResourceRecordSets` MaxItems 300; both are strings. Hosted zone ids are the `Z…` suffix. Private hosted zones are skipped unless `include_private_zones`. Alias targets become `ALIAS` observations. IAM: `route53:ListHostedZones`, `route53:ListResourceRecordSets`.
- **AliDNS:** HMAC-SHA1 V2 (official ECS vector `9NaGiOspFP5UPcwX8Iwt2YJXXuk=`). The signed query string is encoded by RAPTOR, not by httpx, so `/` and `=` in `Signature` become `%2F` / `%3D`. `DescribeDomains` PageSize 100; `DescribeDomainRecords` PageSize 500. `Status=DISABLE` records are skipped. Optional `config.endpoint` overrides `https://alidns.aliyuncs.com/`.
- **Azure DNS:** Entra v2 `client_credentials` against `login.microsoftonline.com/{tenant}/oauth2/v2.0/token`, scope `https://management.azure.com/.default`. Zones: `GET /subscriptions/{id}/providers/Microsoft.Network/dnszones?api-version=2018-05-01`. Record sets: `.../resourceGroups/{rg}/providers/Microsoft.Network/dnsZones/{zone}/recordsets`. `zoneType=Private` skipped. Follows `nextLink`.
- **Google Cloud DNS:** service-account JWT (`RS256`) exchanged at `https://oauth2.googleapis.com/token` for `https://www.googleapis.com/auth/ndev.clouddns.readonly`. `GET /dns/v1/projects/{project}/managedZones` then `.../managedZones/{zone}/rrsets`. `visibility=private` skipped. `nextPageToken` pagination.

## APIs

Admin/manager (admin-only in this slice, matching collectors):

| Method | Path | Notes |
|--------|------|--------|
| GET/POST | `/admin/dns-sources` | List/create cloud connectors. Secrets write-only. |
| PATCH | `/admin/dns-sources/<id>` | Rename, enable, rotate token, zone filters. |
| DELETE | `/admin/dns-sources/<id>` | Deletes the connector and its secrets. Observations keep their history (`source_id` is nulled). Hosts are not deleted. |
| GET | `/admin/dns-sources/<id>/zones` | Last-seen hosted zones from observations. |
| POST | `/admin/dns-sources/<id>/sync-now` | Enqueues `dns_sync` with `{ source_id }`. |
| POST | `/admin/domains/refresh` | Collect-now + enqueue enabled cloud pulls. |
| POST | `/api/records/<id>/resolve-sync-conflict` | Manual adopt, or `{ ip_address }` / `{ source_id }` for multi-source. |
| GET | `/api/records/<id>` | Includes `seen_by` (sources with this FQDN in their latest A batch). |

Collector enroll/ingest URLs are unchanged.

## Interface

Admin → Domains Management → **Cloud DNS** tab (alongside Collectors and IP Sources). Collectors topology stays agents-only.

Host / asset page shows a **Seen by** line. Conflict copy covers multi-source IP disagreement, not only “manual matches import.”

## Phase 1 / 2 compatibility

Collector `INSERT INTO records` still omits `environment_id` / `in_scope`. Coverage KPIs still use `in_scope`, so a Cloudflare dump does not inflate prod coverage until a human files the hosts.

## Phase 4 handoff

Observations already hold AAAA/CNAME/TXT/MX/NS (and provider ids). Phase 4 may project AAAA and CNAME-to-A, and attach dangling-CNAME / cert / HTTP checks, without re-fetching cloud zones.
