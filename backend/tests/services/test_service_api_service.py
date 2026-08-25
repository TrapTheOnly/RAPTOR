from datetime import datetime, timedelta, timezone

from app.services import service_api_service
from app.services import keycloak_identity_service as identity


def test_authenticate_service_api_key_rejects_expired_key(monkeypatch):
    now = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(service_api_service, "_utc_now", lambda: now)
    monkeypatch.setattr(
        service_api_service,
        "get_service_account_key_by_fingerprint",
        lambda fingerprint: {
            "key_id": 5,
            "api_key": "raptor_sk_example_value_1234567890",
            "expires_at": (now - timedelta(minutes=1)).isoformat(),
            "scopes": ["records.read"],
            "service_account_id": 11,
            "username": "svc.reader",
        },
    )

    payload, status = service_api_service.authenticate_service_api_key(
        "raptor_sk_example_value_1234567890",
        "records.read",
    )

    assert status == 401
    assert payload["error"] == "API key expired. Rotate the key."


def test_authenticate_service_api_key_updates_last_used(monkeypatch):
    now = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    touched = []
    monkeypatch.setattr(service_api_service, "_utc_now", lambda: now)
    monkeypatch.setattr(identity, "verify_service_account_secret", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        service_api_service,
        "get_service_account_key_by_fingerprint",
        lambda fingerprint: {
            "key_id": 9,
            "api_key": "raptor_sk_valid_key_value_1234567890",
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "scopes": ["records.read", "pentests.read"],
            "service_account_id": 22,
            "username": "svc.reader",
        },
    )
    monkeypatch.setattr(
        service_api_service,
        "touch_service_api_key_last_used",
        lambda key_id, used_at: touched.append((key_id, used_at)),
    )

    payload, status = service_api_service.authenticate_service_api_key(
        "raptor_sk_valid_key_value_1234567890",
        "records.read",
    )

    assert status == 200
    assert payload["service_account"]["username"] == "svc.reader"
    assert touched and touched[0][0] == 9


def test_authenticate_service_api_key_does_not_require_plaintext(monkeypatch):
    now = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(service_api_service, "_utc_now", lambda: now)
    monkeypatch.setattr(identity, "verify_service_account_secret", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        service_api_service,
        "get_service_account_key_by_fingerprint",
        lambda fingerprint: {
            "key_id": 9,
            "api_key": None,
            "api_key_hash": fingerprint,
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "scopes": ["records.read"],
            "service_account_id": 22,
            "username": "svc.reader",
        },
    )
    monkeypatch.setattr(
        service_api_service,
        "touch_service_api_key_last_used",
        lambda key_id, used_at: None,
    )

    payload, status = service_api_service.authenticate_service_api_key(
        "raptor_sk_valid_key_value_1234567890",
        "records.read",
    )

    assert status == 200
    assert payload["service_account"]["username"] == "svc.reader"


def test_authenticate_service_api_key_rejects_when_keycloak_denies(monkeypatch):
    now = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(service_api_service, "_utc_now", lambda: now)
    monkeypatch.setattr(identity, "verify_service_account_secret", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        service_api_service,
        "get_service_account_key_by_fingerprint",
        lambda fingerprint: {
            "key_id": 9,
            "api_key": "raptor_sk_valid_key_value_1234567890",
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "scopes": ["records.read"],
            "service_account_id": 22,
            "username": "svc.reader",
        },
    )

    payload, status = service_api_service.authenticate_service_api_key(
        "raptor_sk_valid_key_value_1234567890",
        "records.read",
    )

    assert status == 401
    assert payload == {"error": "Unauthorized access."}
