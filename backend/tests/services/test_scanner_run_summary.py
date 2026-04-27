import importlib
import sys
import types
from pathlib import Path


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
