from app.services.llm.connections_service import build_scan_job
from app.services.llm.local_llm_service import fetch_local_status


def test_build_scan_job_is_provider_neutral(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.connections_service.get_connection",
        lambda *_args, **_kwargs: {
            "id": 4,
            "type": "openai",
            "display_name": "OpenAI prod",
            "enabled": True,
            "config": {
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
            },
            "models": [
                {
                    "id": "gpt-4.1",
                    "selected": True,
                    "tools": True,
                    "input_cost_per_1m": 2,
                    "output_cost_per_1m": 8,
                }
            ],
        },
    )
    job, error = build_scan_job(
        12,
        {
            "active_connection_id": 4,
            "active_model_id": "gpt-4.1",
            "cost_limit_usd": 5,
            "thinking_budget_tokens": 8000,
            "max_turns": 40,
        },
        allow_destructive=False,
    )
    assert error is None
    assert "bedrock_model_id" not in job
    assert job["protocol"] == "openai"
    assert job["provider_type"] == "openai"
    assert job["model_id"] == "gpt-4.1"
    assert job["base_url"] == "https://api.openai.com/v1"
    assert job["api_key"] == "sk-test"
    assert job["max_turns"] == 40


def test_build_scan_job_local_skips_aws(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.connections_service.get_connection",
        lambda *_args, **_kwargs: {
            "id": 1,
            "type": "local",
            "display_name": "RAPTOR Local",
            "enabled": True,
            "config": {},
            "models": [{"id": "qwen3.6-27b", "selected": True, "tools": True}],
        },
    )
    monkeypatch.setattr(
        "app.services.llm.local_llm_service.fetch_local_status",
        lambda: {"state": "ready"},
    )
    job, error = build_scan_job(
        9,
        {"active_connection_id": 1, "active_model_id": "qwen3.6-27b", "max_turns": 20},
        allow_destructive=False,
    )
    assert error is None
    assert job["provider_type"] == "local"
    assert job["protocol"] == "openai"
    assert job["base_url"] == "http://local-llm:8084/v1"
    assert job["input_cost_per_1m"] == 0
    assert job["output_cost_per_1m"] == 0
    assert not job["aws_region"] or job["aws_region"] == "us-east-1"
    assert job["api_key"] == ""


def test_fetch_local_status_unreachable(monkeypatch):
    class Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr("app.services.llm.local_llm_service.httpx.Client", Boom)
    status = fetch_local_status()
    assert status["ready"] is False
    assert status["state"] == "unavailable"
