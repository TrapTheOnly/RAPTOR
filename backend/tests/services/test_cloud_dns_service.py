from app.services.cloud_dns_service import sync_all_pull_sources
from app.services.ingest import secrets as secret_mod


def test_encrypt_config_round_trip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "phase3-test-secret-key")
    stored = secret_mod.encrypt_config({"api_token": "cf-live-token", "interval_seconds": 3600})
    assert stored["api_token"].startswith("enc:")
    assert stored["api_token"] != "cf-live-token"
    plain = secret_mod.decrypt_config(stored)
    assert plain["api_token"] == "cf-live-token"
    masked = secret_mod.mask_config(plain)
    assert masked["api_token"] == secret_mod.MASK


def test_sync_all_pull_sources_skips_bind_agent(monkeypatch):
    synced = []

    monkeypatch.setattr(
        "app.services.cloud_dns_service.list_dns_sources",
        lambda **kwargs: [
            {"id": 2, "type": "cloudflare", "enabled": True, "display_name": "cf", "config": {}},
        ],
    )
    monkeypatch.setattr(
        "app.services.cloud_dns_service.sync_pull_source",
        lambda source_id, force=False: synced.append((source_id, force)) or {"ok": True, "skipped": False},
    )

    result = sync_all_pull_sources(force=False)
    assert result["ok"] is True
    assert synced == [(2, False)]


def test_delete_cloud_source_drops_row_and_keeps_hosts(monkeypatch):
    from app.services import cloud_dns_service

    deleted = []
    monkeypatch.setattr(
        cloud_dns_service,
        "get_dns_source",
        lambda source_id, **kwargs: {
            "id": source_id,
            "type": "cloudflare",
            "display_name": "Prod CF",
            "key": "cf-prod",
        },
    )
    monkeypatch.setattr(
        cloud_dns_service,
        "delete_dns_source",
        lambda source_id: deleted.append(source_id) or True,
    )
    monkeypatch.setattr(cloud_dns_service, "record_audit_event", lambda **kwargs: None)

    payload, status = cloud_dns_service.delete_cloud_source_service(3, "awadmin")
    assert status == 200
    assert deleted == [3]
    assert payload["ok"] is True
    assert "kept" in payload["message"].lower()


def test_sync_pull_source_skips_deleted_connector(monkeypatch):
    from app.services import cloud_dns_service

    monkeypatch.setattr(cloud_dns_service, "get_dns_source", lambda *args, **kwargs: None)
    result = cloud_dns_service.sync_pull_source(9, force=True)
    assert result["skipped"] is True
    assert result["reason"] == "deleted"
