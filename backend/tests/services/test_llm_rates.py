from app.services.llm.connections_service import build_scan_job
from app.services.llm.rates import documented_rates


def test_documented_rates_match_anthropic_list_price():
    assert documented_rates("claude-sonnet-4-5") == (3.0, 15.0)
    assert documented_rates("anthropic.claude-sonnet-4-5-v1") == (3.0, 15.0)
    assert documented_rates("claude-haiku-4.5") == (1.0, 5.0)
    assert documented_rates("qwen3.6-27b") is None


def test_build_scan_job_uses_documented_rates_not_policy_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.connections_service.get_connection",
        lambda *_args, **_kwargs: {
            "id": 4,
            "type": "anthropic",
            "display_name": "Anthropic",
            "enabled": True,
            "config": {"api_key": "sk-ant"},
            "models": [{"id": "claude-sonnet-4-5", "selected": True, "tools": True}],
        },
    )
    job, error = build_scan_job(
        12,
        {
            "active_connection_id": 4,
            "active_model_id": "claude-sonnet-4-5",
            "cost_limit_usd": 5,
            "input_cost_per_1m": 3,
            "output_cost_per_1m": 15,
        },
        allow_destructive=False,
    )
    assert error is None
    assert job["input_cost_per_1m"] == 3.0
    assert job["output_cost_per_1m"] == 15.0


def test_build_scan_job_unknown_model_has_zero_cost(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.connections_service.get_connection",
        lambda *_args, **_kwargs: {
            "id": 4,
            "type": "openai_compat",
            "display_name": "Custom",
            "enabled": True,
            "config": {"api_key": "sk", "base_url": "https://example.invalid/v1"},
            "models": [{"id": "my-finetune", "selected": True, "tools": True}],
        },
    )
    job, error = build_scan_job(
        12,
        {
            "active_connection_id": 4,
            "active_model_id": "my-finetune",
            "input_cost_per_1m": 3,
            "output_cost_per_1m": 15,
        },
        allow_destructive=False,
    )
    assert error is None
    assert job["input_cost_per_1m"] == 0
    assert job["output_cost_per_1m"] == 0
