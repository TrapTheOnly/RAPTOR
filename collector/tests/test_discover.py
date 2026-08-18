from raptor_collector.discover import discover_bind


def test_discover_bind_reads_zone_file(tmp_path):
    named = tmp_path / "named.conf"
    zone_file = tmp_path / "db.example.com"
    zone_file.write_text(
        "$ORIGIN example.com.\n@ IN SOA ns1.example.com. admin.example.com. 2024010101 3600 600 86400 3600\nwww IN A 10.0.0.2\n",
        encoding="utf-8",
    )
    named.write_text(
        f'zone "example.com" {{ type master; file "{zone_file}"; }};\n',
        encoding="utf-8",
    )
    zones = discover_bind(str(named))
    assert len(zones) == 1
    assert zones[0].name == "example.com"
    assert zones[0].soa_serial == "2024010101"
    assert any(record.fqdn == "www.example.com" and record.rrtype == "A" for record in zones[0].records)
