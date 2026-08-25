import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCANNER_ROOT = REPO_ROOT / "scanner"
if str(SCANNER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCANNER_ROOT))


def test_build_scan_settings_ignores_job_kali_url():
    settings_mod = importlib.import_module("scanner.settings")
    service = settings_mod.ServiceSettings(
        host="0.0.0.0",
        port=8082,
        scanner_internal_token="token",
        mcp_base_url="http://mcp:8081",
        mcp_server_token="mcp",
        max_concurrent_scans=2,
        kali_server_url="http://kali:5000",
        kali_client_path="/opt/client.py",
    )
    settings = settings_mod.build_scan_settings(
        {
            "record_id": 1,
            "provider_type": "bedrock",
            "protocol": "anthropic",
            "model_id": "model",
            "aws_region": "us-east-1",
            "kali_server_url": "http://evil.example",
            "allow_destructive_tools": True,
        },
        service,
    )
    assert settings.kali_server_url == "http://kali:5000"
    assert settings.allow_destructive_tools is True
    assert settings.model_id == "model"
    assert settings.record_ids == (1,)
    assert settings.wave_id == 0


def test_build_scan_settings_accepts_wave_hosts():
    settings_mod = importlib.import_module("scanner.settings")
    service = settings_mod.ServiceSettings(
        host="0.0.0.0",
        port=8082,
        scanner_internal_token="token",
        mcp_base_url="http://mcp:8081",
        mcp_server_token="mcp",
        max_concurrent_scans=2,
        kali_server_url="http://kali:5000",
        kali_client_path="/opt/client.py",
    )
    settings = settings_mod.build_scan_settings(
        {
            "record_id": 1,
            "record_ids": [1, 2],
            "hosts": [
                {"record_id": 1, "name": "app.example", "ip_address": "10.0.0.1"},
                {"record_id": 2, "name": "api.example", "ip_address": "10.0.0.2"},
            ],
            "wave_id": 9,
            "job_id": 4,
            "provider_type": "bedrock",
            "protocol": "anthropic",
            "model_id": "model",
        },
        service,
    )
    assert settings.record_id == 1
    assert settings.record_ids == (1, 2)
    assert settings.wave_id == 9
    assert settings.job_id == 4
    assert settings.hosts[1]["name"] == "api.example"


def test_build_scan_settings_operator_brief_and_skip_ports():
    settings_mod = importlib.import_module("scanner.settings")
    service = settings_mod.ServiceSettings(
        host="0.0.0.0",
        port=8082,
        scanner_internal_token="token",
        mcp_base_url="http://mcp:8081",
        mcp_server_token="mcp",
        max_concurrent_scans=2,
        kali_server_url="http://kali:5000",
        kali_client_path="/opt/client.py",
    )
    settings = settings_mod.build_scan_settings(
        {
            "record_id": 1,
            "provider_type": "bedrock",
            "protocol": "anthropic",
            "model_id": "model",
            "operator_brief": "Focus on IDOR. Do not brute-force.",
            "skip_port_discovery": True,
            "max_turns": 12,
        },
        service,
    )
    assert settings.operator_brief.startswith("Focus on IDOR")
    assert settings.skip_port_discovery is True
    assert settings.max_turns == 12
