from flask import Blueprint, Response, jsonify, request, send_file, session

from app.http.decorators.admin_required import admin_required
from app.http.request_utils import parse_json_object
from app.services import collector_service
from app.services.collector_dist import artifact_path, version_payload

collector_bp = Blueprint("collector", __name__)


def _collector_token() -> str:
    header = str(request.headers.get("X-Collector-Token") or "").strip()
    if header:
        return header
    auth = str(request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _peer_ip() -> str:
    return collector_service.peer_ip_from_request(
        request.headers.get("X-Forwarded-For", ""),
        request.remote_addr or "",
    )


def _public_base_url() -> str:
    override = str(request.args.get("url") or "").strip().rstrip("/")
    if override:
        return override
    return request.url_root.rstrip("/")


@collector_bp.route("/admin/collectors", methods=["GET"])
@admin_required
def admin_list_collectors():
    payload, status_code = collector_service.list_collectors_service(
        request.args.get("limit"),
        request.args.get("offset"),
        request.args.get("q", ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/enroll-tokens", methods=["POST"])
@admin_required
def admin_create_enroll_token():
    payload, status_code = collector_service.create_enroll_token_service(
        parse_json_object(),
        actor_username=str(session.get("username") or ""),
        public_base_url=_public_base_url(),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/<int:agent_id>", methods=["PATCH"])
@admin_required
def admin_rename_collector(agent_id: int):
    payload, status_code = collector_service.rename_collector_service(
        agent_id,
        parse_json_object(),
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/<int:agent_id>", methods=["DELETE"])
@admin_required
def admin_delete_collector(agent_id: int):
    payload, status_code = collector_service.delete_collector_service(
        agent_id,
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/<int:agent_id>/revoke", methods=["POST"])
@admin_required
def admin_revoke_collector(agent_id: int):
    payload, status_code = collector_service.revoke_collector_service(
        agent_id,
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/<int:agent_id>/rotate", methods=["POST"])
@admin_required
def admin_rotate_collector(agent_id: int):
    payload, status_code = collector_service.rotate_collector_service(
        agent_id,
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/<int:agent_id>/ping", methods=["POST"])
@admin_required
def admin_ping_collector(agent_id: int):
    payload, status_code = collector_service.ping_collector_service(agent_id)
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/<int:agent_id>/collect-now", methods=["POST"])
@admin_required
def admin_collect_now(agent_id: int):
    payload, status_code = collector_service.collect_now_service(
        agent_id,
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/collectors/collect-now", methods=["POST"])
@admin_required
def admin_collect_now_all():
    payload, status_code = collector_service.collect_now_all_service(
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/admin/domains/refresh", methods=["POST"])
@admin_required
def admin_refresh_domains():
    payload, status_code = collector_service.refresh_domains_service(
        actor_username=str(session.get("username") or ""),
    )
    return jsonify(payload), status_code


@collector_bp.route("/collector/v1/enroll", methods=["POST"])
def collector_enroll():
    payload, status_code = collector_service.enroll_agent_service(
        parse_json_object(),
        last_seen_ip=_peer_ip(),
    )
    return jsonify(payload), status_code


@collector_bp.route("/collector/v1/heartbeat", methods=["POST"])
def collector_heartbeat():
    agent = collector_service.authenticate_collector_token(_collector_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = collector_service.heartbeat_service(
        agent,
        parse_json_object(),
        last_seen_ip=_peer_ip(),
    )
    return jsonify(payload), status_code


@collector_bp.route("/collector/v1/ingest", methods=["POST"])
def collector_ingest():
    agent = collector_service.authenticate_collector_token(_collector_token())
    if not agent:
        return jsonify({"error": "Unauthorized access."}), 401
    payload, status_code = collector_service.ingest_service(
        agent,
        parse_json_object(),
        last_seen_ip=_peer_ip(),
    )
    return jsonify(payload), status_code


@collector_bp.route("/collector/v1/version", methods=["GET"])
def collector_version():
    return jsonify(version_payload()), 200


@collector_bp.route("/collector/v1/download/<artifact>", methods=["GET"])
def collector_download(artifact: str):
    if artifact in {"install.ps1", "windows.ps1"}:
        return Response(_windows_install_script(), mimetype="text/plain")
    if artifact in {"install.sh", "linux.sh"}:
        return Response(_linux_install_script(), mimetype="text/x-shellscript")
    path = artifact_path(artifact)
    if not path:
        return jsonify({"error": "Collector package is not available. Rebuild RAPTOR with collector binaries."}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


def _linux_install_script() -> str:
    base = _public_base_url()
    return f"""#!/bin/sh
set -eu
RAPTOR_URL="${{RAPTOR_URL:-{base}}}"
TOKEN="${{1:-}}"
NAME="${{2:-$(hostname -s 2>/dev/null || hostname)}}"
MODE="${{3:-one-sided}}"
ARCH=$(uname -m)
case "$ARCH" in
  x86_64|amd64) ART=linux-amd64 ;;
  aarch64|arm64) ART=linux-arm64 ;;
  *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;;
esac
if [ -z "$TOKEN" ]; then
  echo "usage: install.sh <enroll-token> [name] [one-sided|two-sided]" >&2
  exit 1
fi
curl -fsSL "$RAPTOR_URL/collector/v1/download/$ART" -o raptor-collector
chmod +x raptor-collector
./raptor-collector setup --url "$RAPTOR_URL" --token "$TOKEN" --name "$NAME" --mode "$MODE"
echo "Installed. On systemd hosts the unit is enabled; in Docker, setup starts the agent in the background. Otherwise run: ./raptor-collector run"
"""


def _windows_install_script() -> str:
    base = _public_base_url()
    return f"""param(
  [Parameter(Mandatory=$true)][string]$Token,
  [string]$Name = $env:COMPUTERNAME,
  [ValidateSet('one-sided','two-sided')][string]$Mode = 'one-sided',
  [string]$RaptorUrl = '{base}',
  [string]$Listen = '0.0.0.0:7444'
)
$ErrorActionPreference = 'Stop'
$destDir = Join-Path $env:ProgramData 'raptor-collector'
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
$exe = Join-Path $destDir 'raptor-collector.exe'
Write-Host "Downloading RAPTOR collector from $RaptorUrl ..."
Invoke-WebRequest -UseBasicParsing -Uri "$RaptorUrl/collector/v1/download/windows-amd64.exe" -OutFile $exe
$setupArgs = @('setup','--url', $RaptorUrl, '--token', $Token, '--name', $Name, '--mode', $Mode)
if ($Mode -eq 'two-sided') {{ $setupArgs += @('--listen', $Listen) }}
& $exe @setupArgs
$action = New-ScheduledTaskAction -Execute $exe -Argument 'run'
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName 'RAPTOR Collector' -Action $action -Trigger $trigger -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName 'RAPTOR Collector'
Write-Host "Collector installed as scheduled task 'RAPTOR Collector'."
"""
