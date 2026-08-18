from raptor_collector.normalize import normalize_fqdn
from raptor_collector.zone import parse_zone_records, soa_serial


def test_trailing_dot_not_appended_to_origin():
    records = parse_zone_records(
        "$ORIGIN example.com.\nwww.example.com. IN A 10.0.0.2\n",
        "example.com",
    )
    assert records[0].fqdn == "www.example.com"
    assert normalize_fqdn("www.example.com.", "example.com") == "www.example.com"


def test_soa_serial_from_folded_record():
    text = """
$ORIGIN example.com.
@ IN SOA ns1.example.com. hostmaster.example.com. (
    2024020202
    3600 600 86400 3600 )
"""
    records = parse_zone_records(text, "example.com")
    assert soa_serial(records) == "2024020202"
