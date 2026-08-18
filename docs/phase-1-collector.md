# Phase 1 — Server collector agent

Engineering spec for RAPTOR’s DNS collector. This is not an in-app docs portal article.

**Status:** implemented  
**Depends on:** Phase 0 `dns_sources` / `dns_observations` / source-scoped missing  
**Non-goals:** Cloudflare / Route 53 / Alibaba pull connectors, AAAA/CNAME attack-surface projection, engagements.

## Goal

Operators download a packaged agent from the RAPTOR admin page, drop it on the DNS host, and enroll once with a token. No Python runtime on DNS servers.

## Packages (served by RAPTOR)

Admin → **Domains Management** (also unauthenticated download URLs the installers use):

| Artifact | URL |
|---|---|
| Linux amd64 | `/collector/v1/download/linux-amd64` |
| Linux arm64 | `/collector/v1/download/linux-arm64` |
| Windows exe | `/collector/v1/download/windows-amd64.exe` |
| Windows installer | `/collector/v1/download/install.ps1` |
| Linux installer | `/collector/v1/download/install.sh` |
| Version manifest | `/collector/v1/version` |

Rebuild RAPTOR (or `make collector-dist`) to refresh the binaries baked into the image.

### Linux

```bash
curl -fsSL https://<raptor>/collector/v1/download/linux-amd64 -o raptor-collector
chmod +x raptor-collector
./raptor-collector setup --url https://<raptor> --token raptor_enroll_… --name "dc01" --mode one-sided
```

`--interval` defaults to **300 seconds** (5 minutes), minimum 30. That is the agent ticker, not RAPTOR’s `UPDATE_TIME` (24h drop-folder parse).

Root setup as root installs `raptor-collector.service` **only when systemd is PID 1**. Docker slim images (Debian/Ubuntu included) are not booted with systemd — `/etc/systemd` can exist anyway, and Debian’s `apt install systemctl` is a fake helper. In that case setup starts `raptor-collector run` in the background and logs to `/var/log/raptor-collector.log`. `--mode two-sided` also starts a health listener (default `:7444`) so RAPTOR can ping `/healthz` and `POST /run`.

### Windows / AD DNS

Download `install.ps1` from the admin page (URL is baked in) or:

```powershell
.\install-raptor-collector.ps1 -Token raptor_enroll_… -Name "DC1" -Mode one-sided
```

The script installs `raptor-collector.exe` under `%ProgramData%\raptor-collector` and a startup scheduled task. On Windows it enumerates zones with `dnscmd /EnumZones` and exports with `/ZonePrint` (Active Directory DNS). If zone print is empty, set `--axfr-server host:53` when AXFR is allowed.

## Contact modes

- **One-sided (airgap):** agent only. RAPTOR cannot open a connection back. Ping is disabled.
- **Two-sided:** agent still pushes on a timer, and RAPTOR may `POST /admin/collectors/<id>/ping` against the agent `callback_url/healthz` and `POST /run` to collect immediately. Setup advertises a non-loopback IPv4 (`http://<ip>:7444`) rather than a Docker short hostname RAPTOR cannot resolve. Ping also falls back to the last IP the agent connected from. Admins can PATCH `callback_url` if the auto-detected address is wrong.

An agent is **live** if its last heartbeat is within `interval_seconds + max(60s, 20% of interval)`. Missing interval falls back to 15 minutes.

## Collect now

- Per agent: `POST /admin/collectors/<id>/collect-now`
- All agents + drop-folder: `POST /admin/domains/refresh`

RAPTOR sets `collect_requested_at`. The next heartbeat returns `{ "collect_now": true }` and clears the flag. Two-sided agents also get `POST callback_url/run` immediately. One-sided agents collect on their next ticker cycle (up to their interval).

Agents **parse locally** and POST JSON. They do not copy zone files to RAPTOR. BIND: `named.conf` + `include`s + `zone { file }`. PowerDNS: `bind-config` or `pdnsutil list-all-zones`. Windows: `dnscmd /EnumZones` + `/ZonePrint`. Optional AXFR if a zone has no records.

The drop-folder path still globs `SHARED_PATH/*_A_Records`, copies into `DATA_PATH` with backups, and parses. That is RAPTOR-side compatibility, not the agent.

## Admin operations

- Rename anytime (`PATCH /admin/collectors/<id>`). The same endpoint updates `callback_url` for two-sided agents.
- Last live / last ingest timestamps, plus the agent’s refresh interval.
- Collect now (queued for one-sided; immediate `/run` for two-sided if reachable).
- Delete: drops the agent row and invalidates the key. A still-running binary is refused on the next ingest.
- Paginated table + orthogonal topology graph (12 agents per graph page) so the UI stays usable at scale.
- Animated packets on a pipe when that agent ingested in the last 90 seconds.

## Ingest contract

`POST /collector/v1/ingest` with `source_id`, SOA serial/cursor, and RRsets. All types go into `dns_observations`. Only **A** records project onto pentest hosts.
