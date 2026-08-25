from app.services.ingest.apply import apply_ingest_batch, project_a_records
from app.services.ingest.models import ResourceRecord


def test_project_a_records_keeps_first_address_and_skips_mx(monkeypatch):
    monkeypatch.setattr("app.services.ingest.apply.determine_source", lambda ip: "Corp")
    records = [
        ResourceRecord(fqdn="www.example.com", rrtype="A", rdata="10.0.0.2"),
        ResourceRecord(fqdn="www.example.com", rrtype="A", rdata="10.0.0.9"),
        ResourceRecord(fqdn="example.com", rrtype="MX", rdata="10 mail.example.com"),
    ]
    projected = project_a_records(records)
    assert projected == [
        {"name": "www.example.com", "ip_address": "10.0.0.2", "source": "Corp"},
    ]


def test_apply_ingest_batch_stores_all_rrs_and_projects_a(monkeypatch):
    stored = []
    projected = []
    monkeypatch.setattr(
        "app.services.ingest.apply.record_observations",
        lambda source_id, records, batch_id, cursor_value=None: stored.append(
            {"source_id": source_id, "records": records, "batch_id": batch_id, "cursor": cursor_value}
        ),
    )
    monkeypatch.setattr(
        "app.services.ingest.apply.store_records_in_db",
        lambda records, source_id=None: projected.append({"records": records, "source_id": source_id}),
    )
    monkeypatch.setattr("app.services.ingest.apply.determine_source", lambda ip: "Corp")
    monkeypatch.setattr(
        "app.services.ingest.apply.get_dns_source",
        lambda source_id, **kwargs: {"id": source_id, "type": "bind_agent"},
    )

    result = apply_ingest_batch(
        7,
        [
            {
                "fqdn": "www.example.com",
                "rrtype": "A",
                "rdata": "10.0.0.2",
                "ttl": 60,
                "zone": "example.com",
                "provider_zone_id": "zone-1",
                "provider_record_id": "rec-1",
            },
            {"fqdn": "example.com", "rrtype": "MX", "rdata": "10 mail.example.com"},
        ],
        batch_id="batch-1",
        cursor="2024010101",
    )

    assert result["stored"] == 2
    assert result["projected"] == 1
    assert stored[0]["source_id"] == 7
    assert stored[0]["cursor"] == "2024010101"
    assert stored[0]["records"][0]["provider_zone_id"] == "zone-1"
    assert stored[0]["records"][0]["provider_record_id"] == "rec-1"
    assert projected[0]["source_id"] == 7
    assert projected[0]["records"][0]["name"] == "www.example.com"
    assert projected[0]["records"][0]["source"] == "Corp"


def test_apply_ingest_batch_groups_cloudflare_ips(monkeypatch):
    projected = []
    grouped = []
    monkeypatch.setattr("app.services.ingest.apply.record_observations", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.services.ingest.apply.store_records_in_db",
        lambda records, source_id=None: projected.append({"records": records, "source_id": source_id}),
    )
    monkeypatch.setattr(
        "app.services.ingest.apply.ensure_ip_sources",
        lambda name, ips: grouped.append({"name": name, "ips": list(ips)}),
    )
    monkeypatch.setattr(
        "app.services.ingest.apply.get_dns_source",
        lambda source_id, **kwargs: {"id": source_id, "type": "cloudflare"},
    )

    result = apply_ingest_batch(
        4,
        [ResourceRecord(fqdn="cdn.example.com", rrtype="A", rdata="1.1.1.1")],
        batch_id="cf-1",
    )

    assert result["projected"] == 1
    assert projected[0]["records"][0]["source"] == "Cloudflare"
    assert grouped == [{"name": "Cloudflare", "ips": ["1.1.1.1"]}]


def test_project_a_records_skips_non_ipv4(monkeypatch):
    monkeypatch.setattr("app.services.ingest.apply.determine_source", lambda ip: "Corp")
    records = [
        ResourceRecord(fqdn="alias.example.com", rrtype="A", rdata="dualstack.aws.amazon.com"),
        ResourceRecord(fqdn="www.example.com", rrtype="A", rdata="10.0.0.2"),
    ]
    projected = project_a_records(records)
    assert projected == [{"name": "www.example.com", "ip_address": "10.0.0.2", "source": "Corp"}]
