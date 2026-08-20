"""Amazon Route 53 pull adapter.

Uses boto3 against the global Route 53 endpoint (signed in us-east-1 by default):
https://docs.aws.amazon.com/Route53/latest/APIReference/API_ListHostedZones.html
https://docs.aws.amazon.com/Route53/latest/APIReference/API_ListResourceRecordSets.html

ListHostedZones returns at most 100 zones per page. ListResourceRecordSets
returns at most 300 resource record sets per page. Alias targets are stored
as ALIAS observations and are not projected unless rdata is an IPv4.
Private hosted zones are skipped unless config.include_private_zones is true.
"""

from typing import Iterable, List, Mapping, Optional

from app.services.ingest.models import ResourceRecord, ZoneSnapshot
from app.services.ingest.zone_filter import zone_allowed

ZONES_MAX_ITEMS = "100"
RECORDS_MAX_ITEMS = "300"


def _client_from_config(config: Mapping, boto3_module=None):
    import boto3

    sdk = boto3_module or boto3
    access_key = str(config.get("access_key_id") or "").strip()
    secret = str(config.get("aws_secret_access_key") or "").strip()
    region = str(config.get("region") or "us-east-1").strip() or "us-east-1"
    role_arn = str(config.get("role_arn") or "").strip()
    session_kwargs = {"region_name": region}
    if access_key and secret:
        session_kwargs["aws_access_key_id"] = access_key
        session_kwargs["aws_secret_access_key"] = secret
    session_factory = getattr(sdk, "Session", None)
    session = session_factory(**session_kwargs) if session_factory else sdk.session.Session(**session_kwargs)
    if role_arn:
        sts = session.client("sts", region_name=region)
        assumed = sts.assume_role(RoleArn=role_arn, RoleSessionName="raptor-dns-sync")
        creds = assumed["Credentials"]
        return session.client(
            "route53",
            region_name=region,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    return session.client("route53", region_name=region)


def _hosted_zone_id(raw: str) -> str:
    return str(raw or "").split("/")[-1].strip()


def _is_private_zone(item: Mapping) -> bool:
    return bool((item.get("Config") or {}).get("PrivateZone"))


class Route53Connector:
    def __init__(self, config: Optional[Mapping] = None, client=None) -> None:
        self.config = dict(config or {})
        self._client = client
        self._zones: dict[str, ZoneSnapshot] = {}

    def _route53(self):
        if self._client is not None:
            return self._client
        return _client_from_config(self.config)

    def list_zones(self) -> List[ZoneSnapshot]:
        client = self._route53()
        snapshots: List[ZoneSnapshot] = []
        marker = None
        include_private = bool(self.config.get("include_private_zones"))
        while True:
            kwargs = {"MaxItems": ZONES_MAX_ITEMS}
            if marker:
                kwargs["Marker"] = marker
            payload = client.list_hosted_zones(**kwargs)
            for item in payload.get("HostedZones") or []:
                if _is_private_zone(item) and not include_private:
                    continue
                name = str(item.get("Name") or "").strip().lower().rstrip(".")
                zone_id = _hosted_zone_id(item.get("Id"))
                if not name or not zone_id:
                    continue
                snapshot = ZoneSnapshot(
                    name=name,
                    soa_serial=str(item.get("ResourceRecordSetCount") or item.get("CallerReference") or ""),
                    provider_zone_id=zone_id,
                )
                if zone_allowed(snapshot, self.config):
                    snapshots.append(snapshot)
            if not payload.get("IsTruncated"):
                break
            marker = payload.get("NextMarker")
            if not marker:
                break
        self._zones = {item.name: item for item in snapshots}
        return snapshots

    def fetch_records(self, zone: str) -> Iterable[ResourceRecord]:
        snapshot = self._zones.get(str(zone or "").strip().lower().rstrip("."))
        if snapshot is None:
            self.list_zones()
            snapshot = self._zones.get(str(zone or "").strip().lower().rstrip("."))
        if snapshot is None or not snapshot.provider_zone_id:
            return []
        client = self._route53()
        records: List[ResourceRecord] = []
        kwargs = {"HostedZoneId": snapshot.provider_zone_id, "MaxItems": RECORDS_MAX_ITEMS}
        while True:
            payload = client.list_resource_record_sets(**kwargs)
            for item in payload.get("ResourceRecordSets") or []:
                records.extend(_records_from_rrset(item, snapshot))
            if not payload.get("IsTruncated"):
                break
            kwargs = {
                "HostedZoneId": snapshot.provider_zone_id,
                "MaxItems": RECORDS_MAX_ITEMS,
                "StartRecordName": payload.get("NextRecordName"),
                "StartRecordType": payload.get("NextRecordType"),
            }
            if payload.get("NextRecordIdentifier"):
                kwargs["StartRecordIdentifier"] = payload.get("NextRecordIdentifier")
        return records


def _records_from_rrset(item: Mapping, snapshot: ZoneSnapshot) -> List[ResourceRecord]:
    fqdn = str(item.get("Name") or "").strip().lower().rstrip(".")
    rrtype = str(item.get("Type") or "").strip().upper()
    ttl = item.get("TTL")
    ttl_int = int(ttl) if ttl not in (None, "") else None
    alias = item.get("AliasTarget") or {}
    if alias.get("DNSName"):
        return [
            ResourceRecord(
                fqdn=fqdn,
                rrtype="ALIAS",
                rdata=str(alias.get("DNSName") or "").strip().rstrip("."),
                ttl=ttl_int,
                zone=snapshot.name,
                provider_zone_id=snapshot.provider_zone_id,
                provider_record_id=f"{fqdn}:{rrtype}:alias",
            )
        ]
    out: List[ResourceRecord] = []
    for value in item.get("ResourceRecords") or []:
        rdata = str(value.get("Value") or "").strip()
        if not fqdn or not rrtype or not rdata:
            continue
        out.append(
            ResourceRecord(
                fqdn=fqdn,
                rrtype=rrtype,
                rdata=rdata,
                ttl=ttl_int,
                zone=snapshot.name,
                provider_zone_id=snapshot.provider_zone_id,
                provider_record_id=f"{fqdn}:{rrtype}:{rdata}",
            )
        )
    return out
