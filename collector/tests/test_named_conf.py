from raptor_collector.named_conf import parse_named_conf, load_bind_zones


def test_parse_named_conf_zones_and_relative_file(tmp_path):
    conf = tmp_path / "named.conf"
    conf.write_text(
        """
options { directory "/var/named"; };
zone "example.com" {
    type master;
    file "db.example.com";
};
include "named.conf.local";
""",
        encoding="utf-8",
    )
    local = tmp_path / "named.conf.local"
    local.write_text(
        'zone "corp.internal" { type master; file "/var/named/db.corp.internal"; };\n',
        encoding="utf-8",
    )
    zones = {zone.name: zone for zone in load_bind_zones(str(conf))}
    assert "example.com" in zones
    assert zones["example.com"].file_path.endswith("db.example.com")
    assert zones["corp.internal"].file_path == "/var/named/db.corp.internal"


def test_parse_named_conf_ignores_comments():
    zones = parse_named_conf(
        """
// zone "skip.example" { type master; file "db.skip"; };
# zone "also.skip" { type master; file "db.also"; };
zone "keep.example" { type master; file "db.keep"; };
""",
        conf_dir="/etc/bind",
    )
    assert [zone.name for zone in zones] == ["keep.example"]
