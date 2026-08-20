"""Cloudflare DNS pull adapter.

Uses the documented v4 REST API:
https://developers.cloudflare.com/api/resources/zones/methods/list/
https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/list/

Auth is ``Authorization: Bearer`` (API token). List Zones allows at most 50
results per page; DNS records allow a much larger page size.
"""

from typing import Iterable, List, Mapping, Optional

import httpx

from app.services.ingest.models import ResourceRecord, ZoneSnapshot
from app.services.ingest.zone_filter import zone_allowed

API_BASE = "https://api.cloudflare.com/client/v4"
ZONES_PER_PAGE = 50
RECORDS_PER_PAGE = 1000


def _as_ttl(raw) -> Optional[int]:
    if raw in (None, "", 1, "1"):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def record_rdata(item: Mapping) -> str:
    """Normalize Cloudflare DNS record content to BIND-like rdata."""
    rrtype = str(item.get("type") or "").strip().upper()
    content = str(item.get("content") or "").strip()
    if rrtype == "MX":
        priority = item.get("priority")
        if priority not in (None, "") and content and not content.split()[0].isdigit():
            return f"{priority} {content}".strip()
        return content
    if rrtype == "SRV":
        data = item.get("data") if isinstance(item.get("data"), Mapping) else {}
        target = str(data.get("target") or "").strip()
        if target:
            return (
                f"{data.get('priority', 0)} {data.get('weight', 0)} "
                f"{data.get('port', 0)} {target}"
            ).strip()
    return content


class CloudflareConnector:
    def __init__(self, config: Optional[Mapping] = None, client: Optional[httpx.Client] = None) -> None:
        self.config = dict(config or {})
        self._client = client
        self._owned: Optional[httpx.Client] = None
        self._zones: dict[str, ZoneSnapshot] = {}

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._owned is None:
            token = str(self.config.get("api_token") or "").strip()
            if not token:
                raise RuntimeError("Cloudflare API token is missing.")
            self._owned = httpx.Client(
                base_url=API_BASE,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30.0,
            )
        return self._owned

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        response = self._http().get(path, params=params or {})
        if response.status_code >= 400:
            message = _cloudflare_error(response)
            raise RuntimeError(message)
        payload = response.json()
        if not payload.get("success", True):
            errors = payload.get("errors") or [{"message": "Cloudflare API error"}]
            raise RuntimeError(errors[0].get("message") or "Cloudflare API error")
        return payload

    def _paginate(self, path: str, extra_params: Optional[dict] = None, *, per_page: int) -> List[dict]:
        page = 1
        rows: List[dict] = []
        while True:
            params = {"page": page, "per_page": per_page, **(extra_params or {})}
            payload = self._get(path, params=params)
            rows.extend(payload.get("result") or [])
            info = payload.get("result_info") or {}
            total_pages = int(info.get("total_pages") or page)
            if page >= total_pages:
                break
            page += 1
        return rows

    def list_zones(self) -> List[ZoneSnapshot]:
        extra: dict = {"status": "active"}
        account_id = str(self.config.get("account_id") or "").strip()
        if account_id:
            extra["account.id"] = account_id
        snapshots: List[ZoneSnapshot] = []
        for item in self._paginate("/zones", extra, per_page=ZONES_PER_PAGE):
            name = str(item.get("name") or "").strip().lower().rstrip(".")
            zone_id = str(item.get("id") or "").strip()
            if not name or not zone_id:
                continue
            snapshot = ZoneSnapshot(
                name=name,
                soa_serial=str(item.get("modified_on") or ""),
                provider_zone_id=zone_id,
            )
            if zone_allowed(snapshot, self.config):
                snapshots.append(snapshot)
        self._zones = {item.name: item for item in snapshots}
        return snapshots

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        snapshot = self._zones.get(str(zone or "").strip().lower().rstrip("."))
        if snapshot is None:
            self.list_zones()
            snapshot = self._zones.get(str(zone or "").strip().lower().rstrip("."))
        if snapshot is None or not snapshot.provider_zone_id:
            return []
        records: List[ResourceRecord] = []
        for item in self._paginate(
            f"/zones/{snapshot.provider_zone_id}/dns_records",
            per_page=RECORDS_PER_PAGE,
        ):
            fqdn = str(item.get("name") or "").strip().lower().rstrip(".")
            rrtype = str(item.get("type") or "").strip().upper()
            rdata = record_rdata(item)
            if not fqdn or not rrtype or not rdata:
                continue
            records.append(
                ResourceRecord(
                    fqdn=fqdn,
                    rrtype=rrtype,
                    rdata=rdata,
                    ttl=_as_ttl(item.get("ttl")),
                    zone=snapshot.name,
                    provider_zone_id=snapshot.provider_zone_id,
                    provider_record_id=str(item.get("id") or "") or None,
                )
            )
        return records


def _cloudflare_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            return str(errors[0].get("message") or errors[0])
    except ValueError:
        pass
    return f"Cloudflare API HTTP {response.status_code}"
