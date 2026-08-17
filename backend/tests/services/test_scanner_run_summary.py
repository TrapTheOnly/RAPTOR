import asyncio
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
SCANNER_ROOT = REPO_ROOT / "scanner"
scanner_root_str = str(SCANNER_ROOT)

if scanner_root_str not in sys.path:
    sys.path.insert(0, scanner_root_str)


def _load_run_module():
    anthropic_stub = types.ModuleType("anthropic")
    anthropic_stub.AnthropicBedrock = object
    anthropic_stub.RateLimitError = type("RateLimitError", (Exception,), {})
    sys.modules.setdefault("anthropic", anthropic_stub)
    mcp_stub = types.ModuleType("mcp")
    mcp_stub.ClientSession = object
    sys.modules["mcp"] = mcp_stub
    mcp_client_stub = types.ModuleType("mcp.client")
    sys.modules["mcp.client"] = mcp_client_stub
    stdio_stub = types.ModuleType("mcp.client.stdio")
    stdio_stub.StdioServerParameters = object
    stdio_stub.stdio_client = lambda *args, **kwargs: None
    sys.modules["mcp.client.stdio"] = stdio_stub
    http_stub = types.ModuleType("mcp.client.streamable_http")
    http_stub.streamablehttp_client = lambda *args, **kwargs: None
    sys.modules["mcp.client.streamable_http"] = http_stub
    return importlib.import_module("scanner.run")


def test_summarize_pentest_result_uses_record_id_not_pentest_row_id():
    run = _load_run_module()

    summary = run._summarize_pentest_result(
        {
            "pentest": {
                "id": 142,
                "record_id": 132,
                "ip_address": "10.0.0.5",
                "dns_name": "target.example.com",
                "tested_by": "alice",
                "scan_status": "running",
                "vulnerabilities": "[]",
            }
        }
    )

    assert "record_id=132" in summary
    assert "pentest_id=142" in summary


def test_discover_ports_uses_nmap_scan_not_execute_command():
    run = _load_run_module()
    called = []

    async def fake_call_tool(mcp, name, args):
        called.append((name, dict(args)))
        if name == "get_pentest":
            return {"pentest": {"open_ports": "", "ip_address": "10.0.0.9"}}
        if name == "nmap_scan":
            return {"stdout": "Host: 10.0.0.9 Ports: 22/open/tcp//ssh///"}
        if name == "update_pentest_ports":
            return {"ok": True}
        raise AssertionError(f"unexpected tool {name}")

    class Reporter:
        async def emit(self, *_args, **_kwargs):
            return None

    with patch.object(run, "call_tool", fake_call_tool):
        asyncio.run(
            run._discover_ports("kali", "raptor", types.SimpleNamespace(record_id=3), Reporter())
        )

    names = [name for name, _args in called]
    assert "execute_command" not in names
    assert "nmap_scan" in names
    nmap_args = next(args for name, args in called if name == "nmap_scan")
    assert nmap_args["target"] == "10.0.0.9"
    assert nmap_args["ports"] == "-"
    assert any(name == "update_pentest_ports" for name, _args in called)
