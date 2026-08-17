from datetime import datetime, timedelta, timezone

from app.services import service_account_service


def test_create_service_account_key_uses_default_rotation_window(monkeypatch):
    now = datetime(2026, 3, 13, 10, 0, tzinfo=timezone.utc)
    create_calls = []
    lookup_rows = [
        {
            "service_account_id": 7,
            "username": "svc.exports",
            "added_date": "2026-03-10T12:00:00+00:00",
            "has_api_key": False,
            "scopes": [],
        },
        {
            "service_account_id": 7,
            "username": "svc.exports",
            "added_date": "2026-03-10T12:00:00+00:00",
            "has_api_key": True,
            "scopes": ["records.read"],
            "api_key": "raptor_sk_generated",
            "key_created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=90)).replace(microsecond=0).isoformat(),
        },
    ]

    monkeypatch.setattr(service_account_service, "_utc_now", lambda: now)
    monkeypatch.setattr(service_account_service, "_generate_api_key", lambda: "raptor_sk_generated")
    monkeypatch.setattr(
        service_account_service,
        "get_service_account_with_key",
        lambda username: lookup_rows.pop(0),
    )
    monkeypatch.setattr(
        service_account_service,
        "create_service_account_key",
        lambda **kwargs: create_calls.append(kwargs),
    )

    payload, status = service_account_service.create_service_account_key_service(
        username="svc.exports",
        data={"scopes": ["records.read"]},
        actor_username="awadmin",
    )

    assert status == 201
    assert payload["service_account"]["api_key"] == "raptor_sk_generated"
    assert len(create_calls) == 1
    created_expires = datetime.fromisoformat(create_calls[0]["expires_at"])
    assert created_expires == (now + timedelta(days=90)).replace(microsecond=0)


def test_update_service_account_scopes_requires_non_empty_list(monkeypatch):
    monkeypatch.setattr(
        service_account_service,
        "get_service_account_with_key",
        lambda username: {
            "service_account_id": 8,
            "username": "svc.reader",
            "has_api_key": True,
            "scopes": ["records.read"],
        },
    )

    payload, status = service_account_service.update_service_account_scopes_service(
        "svc.reader",
        {"scopes": []},
    )

    assert status == 400
    assert payload["error"] == "At least one scope is required."


def test_view_service_account_key_returns_gone(monkeypatch):
    monkeypatch.setattr(
        service_account_service,
        "get_service_account_with_key",
        lambda username: {
            "service_account_id": 8,
            "username": "svc.reader",
            "has_api_key": True,
            "scopes": ["records.read"],
        },
    )

    payload, status = service_account_service.view_service_account_key_service("svc.reader")

    assert status == 410
    assert "Rotate" in payload["error"]
