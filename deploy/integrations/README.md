# Local Jira + DefectDojo for RAPTOR

Separate Docker Compose stack. It is **not** part of `docker-compose.dev.yml`.
Jira and DefectDojo join `raptor_app_network` so the RAPTOR app container can reach them.

## Start

RAPTOR should already be running (`./scripts/docker_runner.sh`). Then:

```bash
./scripts/start-integrations.sh
```

| Product | Browser | From RAPTOR (Docker Desktop) | From RAPTOR (compose DNS) |
| --- | --- | --- | --- |
| Jira Software 9.12 | http://localhost:8090 | http://host.docker.internal:8090 | http://jira:8080 |
| DefectDojo 2.51 | http://localhost:8088 | http://host.docker.internal:8088 | http://dojo:8080 |

Prefer `host.docker.internal` in RAPTOR so ticket/finding links open in your browser.
Use the compose DNS names if that hostname does not resolve inside `raptor-dev`.

Seeded credentials are written to `deploy/integrations/generated/credentials.json`.

Default logins (lab only):

- Jira: `admin` / `RaptoR!jira1`
- DefectDojo: `admin` / `RaptoR!dojo1`

## Jira license

The compose stack applies Atlassian’s official **3-hour Data Center timebomb** so setup can finish unattended.

Get a 30-day evaluation from [my.atlassian.com](https://my.atlassian.com) (Jira Software Data Center), then:

```bash
export JIRA_LICENSE='paste-the-key-without-line-breaks'
./scripts/start-integrations.sh
```

If Jira was already licensed with the timebomb, paste the evaluation under **Administration → Applications → Versions & licenses**.

## What the seeders create

### Jira

- Company-managed projects **SEC** (kanban, Security Findings) and **APP** (scrum, Application Backlog)
- Issue types include **Bug** and **Task** (plus **Vulnerability** when the API allows it)
- RAPTOR demo users from `scripts/seed_demo_world.py` (plus `awadmin`), password `RaptorDemo123!`. The timebomb license has **10 Jira Software seats**; pentesters are licensed first. Everyone still exists as an assignee.
- Components: Authentication, API, Cloud, Client
- Version: Current pentest
- Custom fields that RAPTOR findings do **not** have (use **Ask when sending** in the mapping UI):
  - Dev Team (select)
  - Project Tag (multi-select)
  - Remediation SLA (select)
  - Business Owner (text)
  - Needs CAB (select)
  - Affected CWE (text)

### DefectDojo

- Product type **RAPTOR**
- Products **RAPTOR Lab** and **Legacy Intranet** (with business criticality, platform, lifecycle — product metadata RAPTOR does not model)
- Engagements **Baseline assessment** / **Decommission review**
- API token for the admin user

Finding fields RAPTOR does not own (they still appear in the mapping editor): mitigation, impact, references, component name/version, unique ID from tool, planned remediation date.

## Connect in RAPTOR

Open **Settings → Integrations**.

### Jira

1. Display name: `Local Jira`
2. URL: `http://host.docker.internal:8090`
3. Auth: **Data Center personal access token** if `credentials.json` contains a PAT; otherwise **Cloud email + API token** with email/username `admin` and the admin password as the token
4. Test connection
5. Template name: `SEC / Bug`
6. Project: **Security Findings (SEC)**
7. Issue type: **Bug**
8. Save the template, then map fields:
   - Summary ← Title
   - Description ← Description
   - Priority ← Severity
   - Labels ← Category (or skip)
   - **Dev Team**, **Project Tag**, **Remediation SLA**, **Needs CAB** → **Ask when sending**
   - Business Owner / Affected CWE → Ask or skip
   - Components / Fix versions → Ask or skip (also not RAPTOR fields)
9. Save mappings. Optionally add a second template `SEC / Task`.

### DefectDojo

1. Display name: `Local DefectDojo`
2. URL: `http://host.docker.internal:8088`
3. API key: from `credentials.json`
4. Test connection
5. Template name: `RAPTOR Lab / per wave`
6. Product: **RAPTOR Lab**
7. Engagement: **One engagement per wave**
8. Test: **Create a RAPTOR test if missing**
9. Map Title / Description / Severity / CVSS from RAPTOR. Set mitigation, impact, references, component name, and planned remediation date to **Ask when sending** (or skip).

Testers then use **Report to Jira** / **Report to DefectDojo** on a wave or a finding. Unmapped “ask” fields show in the send wizard.

## Stop / reset

```bash
docker compose -f deploy/integrations/docker-compose.yml down
# wipe lab data:
docker compose -f deploy/integrations/docker-compose.yml down -v
```
