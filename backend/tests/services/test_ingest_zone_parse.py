from app.services.ingest.zone_parse import parse_zone_records, soa_serial_from_records


ZONE = """
$TTL 3600
$ORIGIN example.com.
@ IN SOA ns1.example.com. admin.example.com. (
        2024010101 ; serial
        3600 600 86400 3600 )
@ IN A 10.0.0.1
www IN A 10.0.0.2
www.example.com. IN A 10.0.0.3
mail IN MX 10 mailhost.example.com.
"""


def test_parse_zone_records_handles_origin_and_trailing_dot():
    records = parse_zone_records(ZONE, "example.com")
    a_records = {(item.fqdn, item.rdata) for item in records if item.rrtype == "A"}
    assert ("example.com", "10.0.0.1") in a_records
    assert ("www.example.com", "10.0.0.2") in a_records
    assert ("www.example.com", "10.0.0.3") in a_records
    assert ("www.example.com.example.com", "10.0.0.3") not in a_records
    mx = [item for item in records if item.rrtype == "MX"]
    assert mx and mx[0].fqdn == "mail.example.com"
    assert soa_serial_from_records(records) == "2024010101"
