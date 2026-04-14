from app.integrations.db.connection import IntegrityError
from app.services import records_service


def test_create_manual_record_success(monkeypatch):
    monkeypatch.setattr(records_service.records_repository, "create_manual_record", lambda **kwargs: {"id": 7})
    monkeypatch.setattr(
        records_service.records_repository,
        "fetch_record_by_id",
        lambda record_id: {"id": record_id, "name": "api.example.com", "origin": "manual"},
    )

    payload, status = records_service.create_manual_record(
        {"name": "API.Example.com", "ip_address": "10.10.10.10"},
        "manager1",
    )

    assert status == 201
    assert payload["status"] == "success"
    assert payload["record"]["name"] == "api.example.com"
    assert payload["record"]["origin"] == "manual"


def test_create_manual_record_rejects_invalid_domain():
    payload, status = records_service.create_manual_record(
        {"name": "invalid_domain", "ip_address": "10.10.10.10"},
        "manager1",
    )

    assert status == 400
    assert payload == {"error": "Valid domain name is required."}


def test_create_manual_record_rejects_duplicate(monkeypatch):
    def _raise_duplicate(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr(records_service.records_repository, "create_manual_record", _raise_duplicate)

    payload, status = records_service.create_manual_record(
        {"name": "api.example.com", "ip_address": "10.10.10.10"},
        "manager1",
    )

    assert status == 409
    assert payload == {"error": "Record already exists."}


def test_resolve_sync_conflict_converts_manual_record(monkeypatch):
    state = {
        "id": 9,
        "name": "api.example.com",
        "origin": "manual",
        "sync_conflict": 1,
        "ip_address": "10.10.10.10",
    }

    monkeypatch.setattr(records_service.records_repository, "fetch_record_by_id", lambda record_id: dict(state))
    monkeypatch.setattr(
        records_service.dns_sync_service,
        "find_live_imported_record",
        lambda domain: {"name": domain, "ip_address": "10.10.10.11", "source": "Other"},
    )

    def _resolve_manual_sync_conflict(**kwargs):
        state.update({"origin": "automated", "sync_conflict": 0, "ip_address": "10.10.10.11"})
        return None

    monkeypatch.setattr(
        records_service.records_repository,
        "resolve_manual_sync_conflict",
        _resolve_manual_sync_conflict,
    )

    payload, status = records_service.resolve_sync_conflict(9, "admin1")

    assert status == 200
    assert payload["record"]["origin"] == "automated"
    assert payload["record"]["sync_conflict"] == 0
    assert payload["record"]["ip_address"] == "10.10.10.11"
