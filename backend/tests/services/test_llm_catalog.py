from app.services.llm.catalog import apply_model_updates, list_models, merge_models, probe_connection
from app.services.llm.recipes import LOCAL_MODEL_ID, resolve_base_url, type_label
from app.services.llm.secrets import MASK, encrypt_config, mask_config


def test_merge_models_keeps_selection_and_manual_ids():
    existing = [
        {"id": "gpt-4.1", "selected": True, "display_name": "Pinned"},
        {"id": "my-custom", "selected": True, "source": "manual"},
    ]
    fetched = [
        {"id": "gpt-4.1", "display_name": "GPT-4.1", "source": "catalog", "tools": True},
        {"id": "gpt-5", "display_name": "GPT-5", "source": "catalog", "tools": True},
    ]
    merged = merge_models(existing, fetched)
    by_id = {item["id"]: item for item in merged}
    assert by_id["gpt-4.1"]["selected"] is True
    assert by_id["gpt-5"]["selected"] is False
    assert by_id["my-custom"]["source"] == "manual"


def test_apply_model_updates_adds_manual():
    updated = apply_model_updates([], [{"id": "kimi-k2.5", "selected": True}])
    assert updated[0]["id"] == "kimi-k2.5"
    assert updated[0]["selected"] is True


def test_oracle_base_url_and_labels():
    assert "us-chicago-1" in resolve_base_url("oracle", {"region": "us-chicago-1"})
    assert type_label("qwen") == "Qwen (DashScope)"
    assert LOCAL_MODEL_ID == "qwen3.6-27b"


def test_secret_masking_never_returns_raw_key():
    encrypted = encrypt_config({"api_key": "sk-live-secret"}, secret_fields=("api_key",))
    assert encrypted["api_key"].startswith("enc:")
    assert "sk-live-secret" not in encrypted["api_key"]
    masked = mask_config({"api_key": "sk-live-secret"}, secret_fields=("api_key",))
    assert masked["api_key"] == MASK


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or ""

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        return self._response

    def post(self, url, headers=None, json=None):
        return self._response


def test_list_models_openai_compat(monkeypatch):
    response = _FakeResponse(200, {"data": [{"id": "gpt-4.1", "object": "model"}]})
    monkeypatch.setattr("app.services.llm.catalog.httpx.Client", lambda **kwargs: _FakeClient(response))
    models = list_models("openai", {"api_key": "sk-test"})
    assert models[0]["id"] == "gpt-4.1"
    assert models[0]["tools"] is True


def test_connection_openai_one_token(monkeypatch):
    response = _FakeResponse(200, {"id": "chatcmpl-1", "choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr("app.services.llm.catalog.httpx.Client", lambda **kwargs: _FakeClient(response))
    ok, message = probe_connection(
        "openai",
        {"api_key": "sk-test"},
        [{"id": "gpt-4.1", "selected": True}],
    )
    assert ok is True
    assert "gpt-4.1" in message
