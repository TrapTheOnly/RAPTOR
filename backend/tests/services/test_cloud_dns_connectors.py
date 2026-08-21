from app.services.ingest.connectors.alidns import (
    AliDnsConnector,
    encoded_query,
    percent_encode,
    sign_rpc_params,
)
from app.services.ingest.connectors.azure import AzureDnsConnector, expand_record_set, resource_group_from_id
from app.services.ingest.connectors.cloudflare import CloudflareConnector, ZONES_PER_PAGE, record_rdata
from app.services.ingest.connectors.gcp import GcpDnsConnector, build_service_account_jwt, rrdatas_from_rrset
from app.services.ingest.connectors.registry import PULL_CONNECTOR_TYPES, build_connector
from app.services.ingest.connectors.route53 import Route53Connector


class ScriptedClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, path, params=None, headers=None):
        self.calls.append((str(path), dict(params or {})))
        payload = self.payloads.pop(0)

        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return payload

        return Response()

    def post(self, path, data=None, headers=None):
        self.calls.append((str(path), dict(data or {})))
        payload = self.payloads.pop(0)

        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return payload

        return Response()


def test_cloudflare_connector_normalizes_proxied_a_and_mx():
    client = ScriptedClient(
        [
            {
                "success": True,
                "result": [{"id": "zone-1", "name": "example.com", "modified_on": "2024-01-01", "status": "active"}],
                "result_info": {"total_pages": 1},
            },
            {
                "success": True,
                "result": [
                    {
                        "id": "rec-1",
                        "name": "www.example.com",
                        "type": "A",
                        "content": "1.1.1.1",
                        "ttl": 1,
                        "proxied": True,
                    },
                    {
                        "id": "rec-2",
                        "name": "mail.example.com",
                        "type": "CNAME",
                        "content": "www.example.com",
                        "ttl": 300,
                    },
                    {
                        "id": "rec-3",
                        "name": "example.com",
                        "type": "MX",
                        "content": "mail.example.com",
                        "priority": 10,
                        "ttl": 300,
                    },
                ],
                "result_info": {"total_pages": 1},
            },
        ]
    )
    connector = CloudflareConnector({"api_token": "token"}, client=client)
    zones = connector.list_zones()
    records = list(connector.fetch_records("example.com"))
    assert client.calls[0][0].endswith("/zones")
    assert client.calls[0][1]["per_page"] == ZONES_PER_PAGE
    assert client.calls[0][1]["status"] == "active"
    assert [zone.name for zone in zones] == ["example.com"]
    assert {(item.fqdn, item.rrtype, item.rdata) for item in records} == {
        ("www.example.com", "A", "1.1.1.1"),
        ("mail.example.com", "CNAME", "www.example.com"),
        ("example.com", "MX", "10 mail.example.com"),
    }
    a_record = next(item for item in records if item.rrtype == "A")
    assert a_record.provider_zone_id == "zone-1"
    assert a_record.provider_record_id == "rec-1"


def test_cloudflare_mx_rdata_matches_bind_shape():
    assert record_rdata({"type": "MX", "content": "mail.example.com", "priority": 10}) == "10 mail.example.com"
    assert record_rdata({"type": "A", "content": "1.1.1.1"}) == "1.1.1.1"


def test_route53_alias_is_not_an_a_record_and_skips_private_zones():
    class FakeRoute53:
        def list_hosted_zones(self, **kwargs):
            return {
                "HostedZones": [
                    {"Id": "/hostedzone/Z1", "Name": "example.com.", "Config": {"PrivateZone": False}},
                    {"Id": "/hostedzone/ZPRIV", "Name": "internal.example.com.", "Config": {"PrivateZone": True}},
                ],
                "IsTruncated": False,
            }

        def list_resource_record_sets(self, **kwargs):
            return {
                "ResourceRecordSets": [
                    {
                        "Name": "www.example.com.",
                        "Type": "A",
                        "AliasTarget": {"DNSName": "d123.cloudfront.net."},
                    },
                    {
                        "Name": "api.example.com.",
                        "Type": "A",
                        "TTL": 60,
                        "ResourceRecords": [{"Value": "10.0.0.8"}],
                    },
                ],
                "IsTruncated": False,
            }

    connector = Route53Connector({}, client=FakeRoute53())
    zones = connector.list_zones()
    assert [zone.name for zone in zones] == ["example.com"]
    records = list(connector.fetch_records("example.com"))
    assert any(item.rrtype == "ALIAS" and item.rdata == "d123.cloudfront.net" for item in records)
    assert any(item.fqdn == "api.example.com" and item.rrtype == "A" and item.rdata == "10.0.0.8" for item in records)


def test_alidns_signature_matches_official_rpc_v2_vector():
    params = {
        "AccessKeyId": "testid",
        "Action": "DescribeDedicatedHosts",
        "Format": "JSON",
        "RegionId": "cn-beijing",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": "edb2b34af0af9a6d14deaf7c1a5315eb",
        "SignatureVersion": "1.0",
        "Timestamp": "2023-03-13T08:34:30Z",
        "Version": "2014-05-26",
    }
    assert percent_encode("a b") == "a%20b"
    assert percent_encode("*") == "%2A"
    assert percent_encode("~") == "~"
    assert sign_rpc_params(params, "testsecret") == "9NaGiOspFP5UPcwX8Iwt2YJXXuk="
    signed = dict(params)
    signed["Signature"] = "9NaGiOspFP5UPcwX8Iwt2YJXXuk="
    query = encoded_query(signed)
    assert "Signature=9NaGiOspFP5UPcwX8Iwt2YJXXuk%3D" in query
    assert "Timestamp=2023-03-13T08%3A34%3A30Z" in query


def test_alidns_connector_keeps_cname_and_skips_disabled():
    client = ScriptedClient(
        [
            {
                "Domains": {"Domain": [{"DomainName": "example.com", "DomainId": "d1", "UpdateTimestamp": "9"}]},
                "TotalCount": 1,
            },
            {
                "DomainRecords": {
                    "Record": [
                        {"RR": "www", "Type": "A", "Value": "10.0.0.4", "TTL": 600, "RecordId": "r1", "Status": "ENABLE"},
                        {"RR": "shop", "Type": "CNAME", "Value": "www.example.com", "TTL": 600, "RecordId": "r2"},
                        {"RR": "old", "Type": "A", "Value": "10.0.0.9", "TTL": 600, "RecordId": "r3", "Status": "DISABLE"},
                    ]
                },
                "TotalCount": 3,
            },
        ]
    )
    connector = AliDnsConnector(
        {"access_key_id": "id", "access_key_secret": "secret"},
        client=client,
    )
    connector.list_zones()
    records = list(connector.fetch_records("example.com"))
    names = {(item.fqdn, item.rrtype, item.rdata) for item in records}
    assert ("www.example.com", "A", "10.0.0.4") in names
    assert ("shop.example.com", "CNAME", "www.example.com") in names
    assert ("old.example.com", "A", "10.0.0.9") not in names
    assert client.calls[0][0].startswith("https://alidns.aliyuncs.com/?")
    assert "Signature=" in client.calls[0][0]
    assert "Action=DescribeDomains" in client.calls[0][0]


def test_azure_connector_skips_private_and_projects_a():
    zone_id = "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/dnsZones/example.com"
    client = ScriptedClient(
        [
            {
                "value": [
                    {
                        "id": zone_id,
                        "name": "example.com",
                        "properties": {"zoneType": "Public", "numberOfRecordSets": 2},
                    },
                    {
                        "id": "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/dnsZones/internal.example.com",
                        "name": "internal.example.com",
                        "properties": {"zoneType": "Private"},
                    },
                ]
            },
            {
                "value": [
                    {
                        "id": f"{zone_id}/A/www",
                        "name": "www",
                        "type": "Microsoft.Network/dnszones/A",
                        "properties": {"TTL": 60, "ARecords": [{"ipv4Address": "1.2.3.4"}]},
                    },
                    {
                        "id": f"{zone_id}/CNAME/shop",
                        "name": "shop",
                        "type": "Microsoft.Network/dnszones/CNAME",
                        "properties": {"CNAMERecord": {"cname": "www.example.com"}},
                    },
                    {
                        "id": f"{zone_id}/A/alias",
                        "name": "alias",
                        "type": "Microsoft.Network/dnszones/A",
                        "properties": {"targetResource": {"id": "/subscriptions/subid/resourceGroups/rg1/providers/Microsoft.Network/trafficManagerProfiles/tm1"}},
                    },
                ]
            },
        ]
    )
    connector = AzureDnsConnector(
        {"subscription_id": "subid", "access_token": "token"},
        client=client,
    )
    zones = connector.list_zones()
    assert [zone.name for zone in zones] == ["example.com"]
    assert resource_group_from_id(zone_id) == "rg1"
    records = list(connector.fetch_records("example.com"))
    names = {(item.fqdn, item.rrtype, item.rdata) for item in records}
    assert ("www.example.com", "A", "1.2.3.4") in names
    assert ("shop.example.com", "CNAME", "www.example.com") in names
    assert any(item.rrtype == "ALIAS" for item in records)
    assert "dnszones" in client.calls[0][0]
    assert client.calls[0][1]["api-version"] == "2018-05-01"


def test_azure_requests_entra_client_credentials_token():
    client = ScriptedClient(
        [
            {"access_token": "arm-token", "token_type": "Bearer", "expires_in": 3600},
            {"value": []},
        ]
    )
    connector = AzureDnsConnector(
        {
            "tenant_id": "tenant-1",
            "client_id": "app-1",
            "client_secret": "secret-1",
            "subscription_id": "subid",
        },
        client=client,
    )
    connector.list_zones()
    assert "oauth2/v2.0/token" in client.calls[0][0]
    assert client.calls[0][1]["grant_type"] == "client_credentials"
    assert client.calls[0][1]["scope"] == "https://management.azure.com/.default"


def test_azure_mx_expand():
    records = expand_record_set(
        {
            "name": "@",
            "type": "Microsoft.Network/dnszones/MX",
            "properties": {"MXRecords": [{"preference": 10, "exchange": "mail.example.com"}]},
        },
        "example.com",
        "zone-id",
    )
    assert records[0].fqdn == "example.com"
    assert records[0].rdata == "10 mail.example.com"


def test_gcp_connector_skips_private_and_keeps_cname():
    client = ScriptedClient(
        [
            {
                "managedZones": [
                    {"name": "public-zone", "dnsName": "example.com.", "id": "1", "visibility": "public"},
                    {"name": "private-zone", "dnsName": "internal.example.com.", "id": "2", "visibility": "private"},
                ]
            },
            {
                "rrsets": [
                    {"name": "www.example.com.", "type": "A", "ttl": 300, "rrdatas": ["8.8.8.8"]},
                    {"name": "shop.example.com.", "type": "CNAME", "ttl": 300, "rrdatas": ["www.example.com."]},
                ]
            },
        ]
    )
    connector = GcpDnsConnector(
        {"project_id": "proj-1", "access_token": "ya29.token"},
        client=client,
    )
    zones = connector.list_zones()
    assert [zone.name for zone in zones] == ["example.com"]
    records = list(connector.fetch_records("example.com"))
    names = {(item.fqdn, item.rrtype, item.rdata) for item in records}
    assert ("www.example.com", "A", "8.8.8.8") in names
    assert ("shop.example.com", "CNAME", "www.example.com") in names
    assert "/dns/v1/projects/proj-1/managedZones" in client.calls[0][0]


def test_gcp_service_account_jwt_is_rs256():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    token = build_service_account_jwt("sa@proj.iam.gserviceaccount.com", pem, now=1_700_000_000)
    parts = token.split(".")
    assert len(parts) == 3


def test_gcp_routing_policy_rrdatas():
    values = rrdatas_from_rrset(
        {"type": "A", "routingPolicy": {"wrr": {"items": [{"rrdatas": ["9.9.9.9"]}]}}}
    )
    assert values == ["9.9.9.9"]


def test_build_connector_registry():
    assert set(PULL_CONNECTOR_TYPES) == {
        "cloudflare",
        "route53",
        "alidns",
        "azure",
        "gcp",
    }
    assert build_connector("azure", {"access_token": "x", "subscription_id": "s"}).__class__.__name__ == "AzureDnsConnector"
    assert build_connector("gcp", {"access_token": "x", "project_id": "p"}).__class__.__name__ == "GcpDnsConnector"
