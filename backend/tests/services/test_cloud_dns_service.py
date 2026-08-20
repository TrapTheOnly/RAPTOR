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
