import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCANNER_ROOT = REPO_ROOT / "scanner"
if str(SCANNER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCANNER_ROOT))


def test_build_scan_settings_accepts_provider_job():
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
            "provider_type": "openai",
            "protocol": "openai",
            "model_id": "gpt-4.1",
            "base_url": "https://api.openai.com/v1",
            "kali_server_url": "http://evil.example",
            "allow_destructive_tools": True,
            "max_turns": 12,
        },
        service,
    )
    assert settings.kali_server_url == "http://kali:5000"
    assert settings.model_id == "gpt-4.1"
    assert settings.protocol == "openai"
    assert settings.max_turns == 12
    assert settings.allow_destructive_tools is True


def test_build_scan_settings_legacy_bedrock_fields():
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
            "record_id": 2,
            "aws_region": "us-east-1",
            "bedrock_model_id": "anthropic.claude-x",
        },
        service,
    )
    assert settings.model_id == "anthropic.claude-x"
    assert settings.protocol == "anthropic"
    assert settings.provider_type == "bedrock"


def test_openai_tool_and_message_mapping():
    openai_chat = importlib.import_module("scanner.llm.openai_chat")
    tools = openai_chat._openai_tools(
        [{"name": "nmap_scan", "description": "scan", "input_schema": {"type": "object"}}]
    )
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "nmap_scan"
    messages = openai_chat._to_openai_messages(
        [{"type": "text", "text": "sys"}],
        [
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "c1", "name": "nmap_scan", "input": {"host": "1.2.3.4"}}
                ],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "open 22"}],
            },
        ],
    )
    assert messages[0]["role"] == "system"
    assert messages[2]["tool_calls"][0]["id"] == "c1"
    assert messages[3]["role"] == "tool"


def test_local_job_does_not_require_aws_fields():
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
            "record_id": 3,
            "provider_type": "local",
            "protocol": "openai",
            "model_id": "qwen3.6-27b",
            "base_url": "http://local-llm:8084/v1",
            "max_turns": 8,
            "input_cost_per_1m": 0,
            "output_cost_per_1m": 0,
        },
        service,
    )
    assert settings.model_id == "qwen3.6-27b"
    assert settings.protocol == "openai"
    assert settings.aws_region == "us-east-1"
    assert settings.api_key == ""


def test_local_cost_tracker_never_trips_dollar_limit():
    cost_mod = importlib.import_module("scanner.cost")
    tracker = cost_mod.TokenTracker(cost_limit_usd=5.0, input_cost_per_1m=0, output_cost_per_1m=0)
    tracker.add(80_000, 20_000)
    assert tracker.cost_usd == 0
    assert tracker.over_limit is False

