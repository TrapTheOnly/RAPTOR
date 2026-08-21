"""Azure DNS pull adapter.

Public Azure DNS (Microsoft.Network/dnszones) via ARM REST 2018-05-01:
https://learn.microsoft.com/en-us/rest/api/dns/zones/list?view=rest-dns-2018-05-01
https://learn.microsoft.com/en-us/rest/api/dns/record-sets/list-by-dns-zone?view=rest-dns-2018-05-01

Auth is a Microsoft Entra app (service principal) using the v2 client-credentials
flow against ``https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token``
with scope ``https://management.azure.com/.default``.
Private DNS zones are skipped unless config.include_private_zones is true.
"""

from typing import Iterable, List, Mapping, Optional
from urllib.parse import quote

import httpx

from app.services.ingest.models import ResourceRecord, ZoneSnapshot
from app.services.ingest.zone_filter import zone_allowed

API_VERSION = "2018-05-01"
ARM_DEFAULT = "https://management.azure.com"
LOGIN_DEFAULT = "https://login.microsoftonline.com"
PAGE_SIZE = 100


def resource_group_from_id(resource_id: str) -> str:
    parts = str(resource_id or "").split("/")
    for index, part in enumerate(parts):
        if part.lower() == "resourcegroups" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def relative_fqdn(relative: str, zone: str) -> str:
    name = str(relative or "").strip().lower().rstrip(".")
    zone_name = str(zone or "").strip().lower().rstrip(".")
    if name in ("", "@"):
        return zone_name
    if name == zone_name or name.endswith(f".{zone_name}"):
        return name
    return f"{name}.{zone_name}"


def expand_record_set(item: Mapping, zone: str, zone_id: str) -> List[ResourceRecord]:
    props = item.get("properties") if isinstance(item.get("properties"), Mapping) else {}
    rrtype = str(item.get("type") or "").rsplit("/", 1)[-1].strip().upper()
    fqdn = relative_fqdn(str(item.get("name") or ""), zone)
    ttl = props.get("TTL")
    ttl_int = int(ttl) if ttl not in (None, "") else None
    record_id = str(item.get("id") or "") or None
    out: List[ResourceRecord] = []

    def add(kind: str, rdata: str) -> None:
        value = str(rdata or "").strip().rstrip(".")
        if not fqdn or not kind or not value:
            return
        out.append(
            ResourceRecord(
                fqdn=fqdn,
                rrtype=kind,
                rdata=value,
                ttl=ttl_int,
                zone=zone,
                provider_zone_id=zone_id,
                provider_record_id=record_id,
            )
        )

    for row in props.get("ARecords") or []:
        add("A", (row or {}).get("ipv4Address"))
    for row in props.get("AAAARecords") or []:
        add("AAAA", (row or {}).get("ipv6Address"))
    cname = props.get("CNAMERecord") if isinstance(props.get("CNAMERecord"), Mapping) else {}
    if cname.get("cname"):
        add("CNAME", cname.get("cname"))
    for row in props.get("MXRecords") or []:
        preference = (row or {}).get("preference")
        exchange = (row or {}).get("exchange")
        if exchange in (None, ""):
            continue
        add("MX", f"{preference} {exchange}".strip() if preference not in (None, "") else exchange)
    for row in props.get("NSRecords") or []:
        add("NS", (row or {}).get("nsdname"))
    for row in props.get("PTRRecords") or []:
        add("PTR", (row or {}).get("ptrdname"))
    for row in props.get("SRVRecords") or []:
        add(
            "SRV",
            f"{(row or {}).get('priority', 0)} {(row or {}).get('weight', 0)} "
            f"{(row or {}).get('port', 0)} {(row or {}).get('target', '')}".strip(),
        )
    for row in props.get("TXTRecords") or []:
        chunks = (row or {}).get("value") or []
        add("TXT", "".join(str(part) for part in chunks))
    for row in props.get("caaRecords") or props.get("CAARecords") or []:
        add("CAA", f"{(row or {}).get('flags', 0)} {(row or {}).get('tag', '')} {(row or {}).get('value', '')}".strip())
    target = props.get("targetResource") if isinstance(props.get("targetResource"), Mapping) else {}
    if target.get("id") and not out:
        add("ALIAS", target.get("id"))
    if rrtype and not out and props:
        # SOA and unknown types still stored if we can find a useful rdata later.
        soa = props.get("SOARecord") if isinstance(props.get("SOARecord"), Mapping) else {}
        if soa.get("host"):
            add("SOA", soa.get("host"))
    return out


class AzureDnsConnector:
    def __init__(self, config: Optional[Mapping] = None, client: Optional[httpx.Client] = None) -> None:
        self.config = dict(config or {})
        self._client = client
        self._owned: Optional[httpx.Client] = None
        self._token: Optional[str] = str(self.config.get("access_token") or "").strip() or None
        self._zones: dict[str, ZoneSnapshot] = {}
        self._zone_groups: dict[str, str] = {}

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._owned is None:
            self._owned = httpx.Client(timeout=30.0)
        return self._owned

    def _arm_base(self) -> str:
        return str(self.config.get("arm_endpoint") or ARM_DEFAULT).rstrip("/")

    def _login_base(self) -> str:
        return str(self.config.get("authority") or LOGIN_DEFAULT).rstrip("/")

    def _bearer(self) -> str:
        if self._token:
            return self._token
        tenant = str(self.config.get("tenant_id") or "").strip()
        client_id = str(self.config.get("client_id") or "").strip()
        secret = str(self.config.get("client_secret") or "").strip()
        if not tenant or not client_id or not secret:
            raise RuntimeError("Azure tenant id, client id, and client secret are required.")
        arm = self._arm_base()
        url = f"{self._login_base()}/{quote(tenant, safe='')}/oauth2/v2.0/token"
        response = self._http().post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": secret,
                "scope": f"{arm}/.default",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        payload = _json(response)
        if response.status_code >= 400 or not payload.get("access_token"):
            raise RuntimeError(_azure_error(payload, response.status_code, "Entra token request failed"))
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
            raise RuntimeError(_azure_error(payload, response.status_code, "Azure DNS API error"))
        return payload

    def _pages(self, url: str, params: Optional[dict] = None) -> Iterable[dict]:
        payload = self._get(url, params=params)
        while True:
            for item in payload.get("value") or []:
                if isinstance(item, dict):
                    yield item
            next_link = str(payload.get("nextLink") or "").strip()
            if not next_link:
                break
            payload = self._get(next_link)

    def list_zones(self) -> List[ZoneSnapshot]:
        subscription = str(self.config.get("subscription_id") or "").strip()
        if not subscription:
            raise RuntimeError("Azure subscription id is required.")
        include_private = bool(self.config.get("include_private_zones"))
        url = f"{self._arm_base()}/subscriptions/{quote(subscription, safe='')}/providers/Microsoft.Network/dnszones"
        snapshots: List[ZoneSnapshot] = []
        self._zone_groups = {}
        for item in self._pages(url, params={"api-version": API_VERSION, "$top": PAGE_SIZE}):
            props = item.get("properties") if isinstance(item.get("properties"), Mapping) else {}
            zone_type = str(props.get("zoneType") or "Public").strip().lower()
            if zone_type == "private" and not include_private:
                continue
            name = str(item.get("name") or "").strip().lower().rstrip(".")
            zone_id = str(item.get("id") or "").strip()
            group = resource_group_from_id(zone_id)
            if not name or not zone_id or not group:
                continue
            snapshot = ZoneSnapshot(
                name=name,
                soa_serial=str(props.get("numberOfRecordSets") or ""),
                provider_zone_id=zone_id,
            )
            if zone_allowed(snapshot, self.config):
                snapshots.append(snapshot)
                self._zone_groups[name] = group
        self._zones = {item.name: item for item in snapshots}
        return snapshots

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        snapshot = self._lookup_zone(zone)
        if snapshot is None:
            return []
        group = self._zone_groups.get(snapshot.name)
        subscription = str(self.config.get("subscription_id") or "").strip()
        if not group or not subscription:
            return []
        url = (
            f"{self._arm_base()}/subscriptions/{quote(subscription, safe='')}"
            f"/resourceGroups/{quote(group, safe='')}"
            f"/providers/Microsoft.Network/dnsZones/{quote(snapshot.name, safe='')}/recordsets"
        )
        records: List[ResourceRecord] = []
        for item in self._pages(url, params={"api-version": API_VERSION, "$top": PAGE_SIZE}):
            records.extend(expand_record_set(item, snapshot.name, snapshot.provider_zone_id))
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


def _azure_error(payload: Mapping, status: int, fallback: str) -> str:
    error = payload.get("error") if isinstance(payload.get("error"), Mapping) else {}
    message = error.get("message") or payload.get("error_description") or payload.get("error")
    if message:
        return str(message)
    return f"{fallback} (HTTP {status})"
