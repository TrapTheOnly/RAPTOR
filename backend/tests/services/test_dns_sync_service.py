from pathlib import Path

from app.services import dns_sync_service


def test_extract_domain_from_filename():
    assert dns_sync_service.extract_domain_from_filename("example.com_A_Records") == "example.com"
    assert dns_sync_service.extract_domain_from_filename("invalid.txt") is None


def test_parse_bind_zone_file_handles_apex_and_hosts(tmp_path, monkeypatch):
    zone_file = tmp_path / "example.com_A_Records"
    zone_file.write_text("@ IN A 10.0.0.1\nwww IN A 10.0.0.2\n", encoding="utf-8")

    monkeypatch.setattr(dns_sync_service, "determine_source", lambda ip: "Corp")

    records = dns_sync_service.parse_bind_zone_file(str(zone_file), "example.com")

    assert records == [
        {"name": "example.com", "ip_address": "10.0.0.1", "source": "Corp"},
        {"name": "www.example.com", "ip_address": "10.0.0.2", "source": "Corp"},
    ]


def test_handle_zone_file_changes_skips_when_matches_latest_backup(tmp_path, monkeypatch):
    backup_root = tmp_path / "backups"
    data_root = tmp_path / "data"
    backup_root.mkdir()
    data_root.mkdir()

    final_file = data_root / "example.com_A_Records"
    incoming_file = tmp_path / "incoming_A_Records"
    incoming_file.write_bytes(b"same-content")

    monkeypatch.setattr(dns_sync_service, "BACKUP_FOLDER", str(backup_root))

    domain_backup_folder = backup_root / "example.com"
    domain_backup_folder.mkdir()
    (domain_backup_folder / "example.com_A_Records-1.bak").write_bytes(b"same-content")

    result = dns_sync_service.handle_zone_file_changes(str(incoming_file), str(final_file))

    assert result is None
    assert not final_file.exists()
