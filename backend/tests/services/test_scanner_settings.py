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
            "aws_region": "us-east-1",
            "bedrock_model_id": "model",
            "kali_server_url": "http://evil.example",
            "allow_destructive_tools": True,
        },
        service,
    )
    assert settings.kali_server_url == "http://kali:5000"
    assert settings.allow_destructive_tools is True
