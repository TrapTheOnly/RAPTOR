import json

from raptor_collector.cli import main
from raptor_collector.client import CollectorClient, CollectorClientError


def test_cli_discover_prints_json(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("RAPTOR_COLLECTOR_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("RAPTOR_BIND_CONF", str(tmp_path / "missing.conf"))
    assert main(["discover"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == []


def test_client_enroll_stores_token(monkeypatch):
    calls = []

    def fake_request(self, method, path, body=None, token=None):
        calls.append((method, path, body, token))
        return {"token": "raptor_col_abc", "source_id": 4, "agent_id": 2}

    monkeypatch.setattr(CollectorClient, "_request", fake_request)
    client = CollectorClient("http://raptor.example")
    result = client.enroll("raptor_enroll_x", "dns01", "1.0.0")
    assert result["source_id"] == 4
    assert client.token == "raptor_col_abc"
    assert calls[0][1] == "/collector/v1/enroll"


def test_run_once_enrolls_when_token_present(monkeypatch, tmp_path):
    from raptor_collector.config import CollectorConfig
    from raptor_collector import run as run_mod

    state_path = tmp_path / "state.json"
    config = CollectorConfig(
        raptor_url="http://raptor.example",
        token="",
        enroll_token="raptor_enroll_x",
        hostname="dns01",
        state_path=state_path,
        bind_conf="",
        powerdns_conf="",
        axfr_server="",
        tsig_name="",
        tsig_secret="",
        tsig_algorithm="hmac-sha256",
        interval_seconds=300,
        extra_zone_dirs=(),
    )
    monkeypatch.setattr(run_mod, "enroll", lambda cfg: run_mod.save_state(cfg.state_path, {"token": "raptor_col_x", "source_id": 3}))
    monkeypatch.setattr(run_mod, "collect_zones", lambda cfg: [])

    class FakeClient:
        def heartbeat(self, zones, version, soa_serial=""):
            return {"source_id": 3}

        def ingest(self, *args, **kwargs):
            raise AssertionError("ingest should not run without records")

    monkeypatch.setattr(run_mod, "_client_from_state", lambda cfg: (FakeClient(), {"token": "raptor_col_x", "source_id": 3}))
    result = run_mod.run_once(config)
    assert result["ingest"] is None


def test_client_error_includes_status():
    err = CollectorClientError("nope", status_code=401)
    assert err.status_code == 401

