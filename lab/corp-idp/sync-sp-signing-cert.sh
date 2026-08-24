#!/usr/bin/env bash
# Import RAPTOR Keycloak's realm signing cert into the lab SAML client so
# AuthnRequests signed by RAPTOR can be verified (saml.client.signature=true).
set -euo pipefail

RAPTOR_KEYCLOAK="${RAPTOR_KEYCLOAK_URL:-http://localhost:8180}"
CORP_IDP="${CORP_IDP_URL:-http://localhost:8280}"
CORP_ADMIN_USER="${CORP_IDP_ADMIN:-admin}"
CORP_ADMIN_PASS="${CORP_IDP_ADMIN_PASSWORD:-corp-admin}"
SP_ENTITY_ID="${RAPTOR_SP_ENTITY_ID:-http://localhost:8180/realms/raptor}"

PASS="$(docker exec raptor-keycloak-dev printenv KC_BOOTSTRAP_ADMIN_PASSWORD)"
TOKEN="$(curl -sS -X POST "${RAPTOR_KEYCLOAK}/realms/master/protocol/openid-connect/token" \
  -d client_id=admin-cli -d username=admin -d "password=${PASS}" -d grant_type=password \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "${RAPTOR_KEYCLOAK}/admin/realms/raptor/keys" \
  | python3 -c '
import json, sys
from pathlib import Path
cert = ""
for key in json.load(sys.stdin).get("keys") or []:
    if key.get("algorithm") == "RS256" and key.get("status") == "ACTIVE" and key.get("use") == "SIG":
        cert = str(key.get("certificate") or "").strip()
        if cert:
            break
if not cert:
    raise SystemExit("No RAPTOR RS256 signing certificate found.")
lines = ["-----BEGIN CERTIFICATE-----"]
for i in range(0, len(cert), 64):
    lines.append(cert[i:i + 64])
lines.append("-----END CERTIFICATE-----")
Path("/tmp/raptor-sp.pem").write_text("\n".join(lines) + "\n")
'

CORP_TOKEN="$(curl -sS -X POST "${CORP_IDP}/realms/master/protocol/openid-connect/token" \
  -d client_id=admin-cli -d "username=${CORP_ADMIN_USER}" -d "password=${CORP_ADMIN_PASS}" -d grant_type=password \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

CLIENT_UUID="$(curl -sS -H "Authorization: Bearer ${CORP_TOKEN}" \
  --get "${CORP_IDP}/admin/realms/corp/clients" --data-urlencode "clientId=${SP_ENTITY_ID}" \
  | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(rows[0]["id"] if rows else "")')"
[[ -n "${CLIENT_UUID}" ]] || { echo "Lab SAML client ${SP_ENTITY_ID} not found." >&2; exit 1; }

curl -sS -o /dev/null -w "upload=%{http_code}\n" -X POST \
  -H "Authorization: Bearer ${CORP_TOKEN}" \
  -F "keystoreFormat=Certificate PEM" \
  -F "file=@/tmp/raptor-sp.pem;type=application/x-pem-file" \
  "${CORP_IDP}/admin/realms/corp/clients/${CLIENT_UUID}/certificates/saml.signing/upload-certificate"

curl -sS -H "Authorization: Bearer ${CORP_TOKEN}" \
  "${CORP_IDP}/admin/realms/corp/clients/${CLIENT_UUID}" \
  | python3 -c '
import json, sys
client = json.load(sys.stdin)
client.setdefault("attributes", {})["saml.client.signature"] = "true"
json.dump(client, sys.stdout)
' > /tmp/corp-saml-client.json

curl -sS -o /dev/null -w "client=%{http_code}\n" -X PUT \
  -H "Authorization: Bearer ${CORP_TOKEN}" -H "Content-Type: application/json" \
  --data @/tmp/corp-saml-client.json \
  "${CORP_IDP}/admin/realms/corp/clients/${CLIENT_UUID}"
echo "Lab SAML client now requires signed AuthnRequests from RAPTOR."
