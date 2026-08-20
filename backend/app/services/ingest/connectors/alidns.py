"""Alibaba Cloud DNS (AliDNS) pull adapter.

RPC style Alidns/2015-01-09 against https://alidns.aliyuncs.com, signed with
HMAC-SHA1 V2 as documented at:
https://www.alibabacloud.com/help/en/sdk/product-overview/rpc-mechanism
https://www.alibabacloud.com/help/en/dns/api-alidns-2015-01-09-overview

DescribeDomains PageSize max is 100. DescribeDomainRecords PageSize max is 500.
Disabled records (Status=DISABLE) are skipped so they are not treated as live.
"""

import base64
import hashlib
import hmac
import time
import uuid
from typing import Iterable, List, Mapping, Optional
from urllib.parse import quote

import httpx

from app.services.ingest.models import ResourceRecord, ZoneSnapshot
from app.services.ingest.zone_filter import zone_allowed

API_ENDPOINT = "https://alidns.aliyuncs.com/"
API_VERSION = "2015-01-09"
DOMAINS_PAGE_SIZE = 100
RECORDS_PAGE_SIZE = 500


def percent_encode(value: str) -> str:
    """Aliyun POP percent-encoding (RFC 3986 plus Java URLEncoder replacements)."""
    return quote(str(value), safe="~").replace("+", "%20").replace("*", "%2A").replace("%7E", "~")


def sign_rpc_params(params: Mapping[str, str], secret: str, method: str = "GET") -> str:
    canonical = "&".join(f"{percent_encode(key)}={percent_encode(params[key])}" for key in sorted(params))
    string_to_sign = f"{method}&{percent_encode('/')}&{percent_encode(canonical)}"
    digest = hmac.new(
        f"{secret}&".encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def encoded_query(params: Mapping[str, str]) -> str:
    return "&".join(f"{percent_encode(key)}={percent_encode(params[key])}" for key in sorted(params))


class AliDnsConnector:
    def __init__(self, config: Optional[Mapping] = None, client: Optional[httpx.Client] = None) -> None:
        self.config = dict(config or {})
        self._client = client
        self._owned: Optional[httpx.Client] = None
        self._zones: dict[str, ZoneSnapshot] = {}

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._owned is None:
            self._owned = httpx.Client(timeout=30.0)
        return self._owned

    def _endpoint(self) -> str:
        raw = str(self.config.get("endpoint") or API_ENDPOINT).strip() or API_ENDPOINT
        if not raw.startswith("http"):
            raw = f"https://{raw}"
        return raw if raw.endswith("/") else f"{raw}/"

    def _call(self, action: str, extra: Optional[Mapping[str, str]] = None) -> dict:
        access_key = str(self.config.get("access_key_id") or "").strip()
        secret = str(self.config.get("access_key_secret") or "").strip()
        if not access_key or not secret:
            raise RuntimeError("Alibaba Cloud AccessKey id and secret are required.")
        params = {
            "Action": action,
            "Format": "JSON",
            "Version": API_VERSION,
            "AccessKeyId": access_key,
            "SignatureMethod": "HMAC-SHA1",
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SignatureVersion": "1.0",
            "SignatureNonce": uuid.uuid4().hex,
            **{str(key): str(value) for key, value in dict(extra or {}).items() if value is not None},
        }
        signed = dict(params)
        signed["Signature"] = sign_rpc_params(params, secret)
        url = f"{self._endpoint()}?{encoded_query(signed)}"
        response = self._http().get(url)
        payload = _json_or_empty(response)
        if response.status_code >= 400 or (payload.get("Code") and payload.get("Message")):
            raise RuntimeError(str(payload.get("Message") or payload.get("Code") or f"AliDNS HTTP {response.status_code}"))
        return payload

    def list_zones(self) -> List[ZoneSnapshot]:
        snapshots: List[ZoneSnapshot] = []
        page = 1
        while True:
            payload = self._call(
                "DescribeDomains",
                {"PageNumber": str(page), "PageSize": str(DOMAINS_PAGE_SIZE)},
            )
            domains = ((payload.get("Domains") or {}).get("Domain") or [])
            for item in domains:
                name = str(item.get("DomainName") or "").strip().lower().rstrip(".")
                if not name:
                    continue
                snapshot = ZoneSnapshot(
                    name=name,
                    soa_serial=str(item.get("UpdateTimestamp") or item.get("VersionCode") or ""),
                    provider_zone_id=str(item.get("DomainId") or name),
                )
                if zone_allowed(snapshot, self.config):
                    snapshots.append(snapshot)
            if not _more_pages(payload, page, DOMAINS_PAGE_SIZE, domains):
                break
            page += 1
        self._zones = {item.name: item for item in snapshots}
        return snapshots

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        snapshot = self._zones.get(str(zone or "").strip().lower().rstrip("."))
        if snapshot is None:
            self.list_zones()
            snapshot = self._zones.get(str(zone or "").strip().lower().rstrip("."))
        if snapshot is None:
            return []
        records: List[ResourceRecord] = []
        page = 1
        while True:
            payload = self._call(
                "DescribeDomainRecords",
                {
                    "DomainName": snapshot.name,
                    "PageNumber": str(page),
                    "PageSize": str(RECORDS_PAGE_SIZE),
                },
            )
            items = ((payload.get("DomainRecords") or {}).get("Record") or [])
            for item in items:
                if str(item.get("Status") or "ENABLE").upper() == "DISABLE":
                    continue
                rrtype = str(item.get("Type") or "").strip().upper()
                rdata = str(item.get("Value") or "").strip()
                fqdn = _fqdn_from_rr(str(item.get("RR") or "").strip(), snapshot.name)
                if not fqdn or not rrtype or not rdata:
                    continue
                ttl_raw = item.get("TTL")
                ttl = int(ttl_raw) if ttl_raw not in (None, "") else None
                records.append(
                    ResourceRecord(
                        fqdn=fqdn,
                        rrtype=rrtype,
                        rdata=rdata,
                        ttl=ttl,
                        zone=snapshot.name,
                        provider_zone_id=snapshot.provider_zone_id,
                        provider_record_id=str(item.get("RecordId") or "") or None,
                    )
                )
            if not _more_pages(payload, page, RECORDS_PAGE_SIZE, items):
                break
            page += 1
        return records


def _more_pages(payload: Mapping, page: int, page_size: int, batch: list) -> bool:
    if not batch:
        return False
    total = int(payload.get("TotalCount") or 0)
    if total:
        return page * page_size < total
    return len(batch) >= page_size


def _fqdn_from_rr(rr_name: str, zone: str) -> str:
    if rr_name in ("", "@"):
        return zone
    lowered = rr_name.lower().rstrip(".")
    if lowered == zone or lowered.endswith(f".{zone}"):
        return lowered
    return f"{lowered}.{zone}"


def _json_or_empty(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}
