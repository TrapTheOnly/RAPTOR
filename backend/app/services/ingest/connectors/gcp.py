"""Google Cloud DNS pull adapter.

Cloud DNS REST v1:
https://cloud.google.com/dns/docs/reference/rest/v1/managedZones/list
https://cloud.google.com/dns/docs/reference/rest/v1/resourceRecordSets/list

Auth is a service-account JWT exchanged at https://oauth2.googleapis.com/token
for scope https://www.googleapis.com/auth/ndev.clouddns.readonly.
Private managed zones are skipped unless config.include_private_zones is true.
"""

import base64
import json
import time
from typing import Iterable, List, Mapping, Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.services.ingest.models import ResourceRecord, ZoneSnapshot
from app.services.ingest.zone_filter import zone_allowed

DNS_API = "https://dns.googleapis.com/dns/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"
READONLY_SCOPE = "https://www.googleapis.com/auth/ndev.clouddns.readonly"
PAGE_SIZE = 500


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_service_account_jwt(
    client_email: str,
    private_key_pem: str,
    *,
    scope: str = READONLY_SCOPE,
    audience: str = TOKEN_URL,
    now: Optional[int] = None,
) -> str:
    issued = int(now if now is not None else time.time())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = b64url(
        json.dumps(
            {
                "iss": client_email,
                "scope": scope,
                "aud": audience,
                "iat": issued,
                "exp": issued + 3600,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{b64url(signature)}"


def parse_service_account(config: Mapping) -> dict:
    raw = config.get("service_account_json")
    parsed = {}
    if isinstance(raw, Mapping):
        parsed = dict(raw)
    elif isinstance(raw, str) and raw.strip():
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GCP service account JSON is invalid.") from exc
        if isinstance(loaded, dict):
            parsed = loaded
    return {
        "project_id": str(config.get("project_id") or parsed.get("project_id") or "").strip(),
        "client_email": str(config.get("client_email") or parsed.get("client_email") or "").strip(),
        "private_key": str(config.get("private_key") or parsed.get("private_key") or "").strip(),
    }


def rrdatas_from_rrset(item: Mapping) -> List[str]:
    values = [str(part).strip() for part in (item.get("rrdatas") or []) if str(part).strip()]
    if values:
        return values
    policy = item.get("routingPolicy") if isinstance(item.get("routingPolicy"), Mapping) else {}
    collected: List[str] = []
    for key in ("wrr", "geo"):
        block = policy.get(key) if isinstance(policy.get(key), Mapping) else {}
        for entry in block.get("items") or []:
            collected.extend(str(part).strip() for part in ((entry or {}).get("rrdatas") or []) if str(part).strip())
    backup = policy.get("primaryBackup") if isinstance(policy.get("primaryBackup"), Mapping) else {}
    targets = backup.get("primaryTargets") if isinstance(backup.get("primaryTargets"), Mapping) else {}
    collected.extend(str(part).strip() for part in (targets.get("externalEndpoints") or []) if str(part).strip())
    return collected


class GcpDnsConnector:
    def __init__(self, config: Optional[Mapping] = None, client: Optional[httpx.Client] = None) -> None:
        self.config = dict(config or {})
        self._client = client
        self._owned: Optional[httpx.Client] = None
        self._token: Optional[str] = str(self.config.get("access_token") or "").strip() or None
        self._zones: dict[str, ZoneSnapshot] = {}
        self._zone_ids: dict[str, str] = {}

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._owned is None:
            self._owned = httpx.Client(timeout=30.0)
        return self._owned

    def _account(self) -> dict:
        return parse_service_account(self.config)

    def _bearer(self) -> str:
        if self._token:
            return self._token
        account = self._account()
        if not account["client_email"] or not account["private_key"]:
            raise RuntimeError("GCP service account JSON (or client email and private key) is required.")
        assertion = build_service_account_jwt(account["client_email"], account["private_key"])
        response = self._http().post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        payload = _json(response)
        if response.status_code >= 400 or not payload.get("access_token"):
            raise RuntimeError(str(payload.get("error_description") or payload.get("error") or "GCP token request failed"))
        self._token = str(payload["access_token"])
        return self._token

    def _get(self, url: str, params: Optional[dict] = None) -> dict:
        response = self._http().get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {self._bearer()}"},
        )
        payload = _json(response)
        if response.status_code >= 400:
            error = payload.get("error") if isinstance(payload.get("error"), Mapping) else {}
            raise RuntimeError(str(error.get("message") or payload.get("error") or f"Cloud DNS HTTP {response.status_code}"))
        return payload

    def list_zones(self) -> List[ZoneSnapshot]:
        project = self._account()["project_id"]
        if not project:
            raise RuntimeError("GCP project id is required.")
        include_private = bool(self.config.get("include_private_zones"))
        snapshots: List[ZoneSnapshot] = []
        self._zone_ids = {}
        page_token = None
        while True:
            params = {"maxResults": PAGE_SIZE}
            if page_token:
                params["pageToken"] = page_token
            payload = self._get(f"{DNS_API}/projects/{project}/managedZones", params=params)
            for item in payload.get("managedZones") or []:
                visibility = str(item.get("visibility") or "public").strip().lower()
                if visibility == "private" and not include_private:
                    continue
                name = str(item.get("dnsName") or "").strip().lower().rstrip(".")
                zone_id = str(item.get("name") or item.get("id") or "").strip()
                if not name or not zone_id:
                    continue
                snapshot = ZoneSnapshot(
                    name=name,
                    soa_serial=str(item.get("nameServerSet") or item.get("id") or ""),
                    provider_zone_id=str(item.get("id") or zone_id),
                )
                if zone_allowed(snapshot, self.config):
                    snapshots.append(snapshot)
                    self._zone_ids[name] = zone_id
            page_token = str(payload.get("nextPageToken") or "").strip() or None
            if not page_token:
                break
        self._zones = {item.name: item for item in snapshots}
        return snapshots

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        snapshot = self._lookup_zone(zone)
        if snapshot is None:
            return []
        project = self._account()["project_id"]
        managed_zone = self._zone_ids.get(snapshot.name)
        if not project or not managed_zone:
            return []
        records: List[ResourceRecord] = []
        page_token = None
        while True:
            params = {"maxResults": PAGE_SIZE}
            if page_token:
                params["pageToken"] = page_token
            payload = self._get(
                f"{DNS_API}/projects/{project}/managedZones/{managed_zone}/rrsets",
                params=params,
            )
            for item in payload.get("rrsets") or []:
                fqdn = str(item.get("name") or "").strip().lower().rstrip(".")
                rrtype = str(item.get("type") or "").strip().upper()
                ttl = item.get("ttl")
                ttl_int = int(ttl) if ttl not in (None, "") else None
                for rdata in rrdatas_from_rrset(item):
                    records.append(
                        ResourceRecord(
                            fqdn=fqdn,
                            rrtype=rrtype,
                            rdata=rdata.rstrip("."),
                            ttl=ttl_int,
                            zone=snapshot.name,
                            provider_zone_id=snapshot.provider_zone_id,
                            provider_record_id=f"{fqdn}:{rrtype}:{rdata}",
                        )
                    )
            page_token = str(payload.get("nextPageToken") or "").strip() or None
            if not page_token:
                break
        return records

    def _lookup_zone(self, zone: str) -> Optional[ZoneSnapshot]:
        key = str(zone or "").strip().lower().rstrip(".")
        snapshot = self._zones.get(key)
        if snapshot is None:
            self.list_zones()
            snapshot = self._zones.get(key)
        return snapshot


def _json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}
