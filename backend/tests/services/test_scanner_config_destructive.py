from app.services import scanner_service


def test_update_scanner_config_accepts_destructive_tools_flag(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        scanner_service,
        "update_scanner_config",
        lambda updates: captured.update(updates),
    )
    monkeypatch.setattr(
        scanner_service,
        "get_scanner_config",
        lambda: {
            "enabled": 1,
            "allow_destructive_tools": 1,
            "aws_region": "us-east-1",
        },
    )

    payload, status = scanner_service.update_scanner_config_payload(
        {"allow_destructive_tools": True},
        "awadmin",
    )

    assert status == 200
    assert captured["allow_destructive_tools"] == 1
    assert payload["config"]["allow_destructive_tools"] == 1
