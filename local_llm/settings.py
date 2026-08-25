import json
import os
from pathlib import Path

DEFINITION_PATH = Path(os.getenv("LOCAL_LLM_DEFINITION", "/opt/raptor-local.json"))
MODELS_DIR = Path(os.getenv("LOCAL_LLM_MODELS_DIR", "/models"))
STATUS_PATH = MODELS_DIR / "status.json"
LLAMA_SERVER_BIN = os.getenv("LLAMA_SERVER_BIN", "/usr/local/bin/llama-server")
INFER_HOST = os.getenv("LOCAL_LLM_INFER_HOST", "0.0.0.0")
INFER_PORT = int(os.getenv("LOCAL_LLM_INFER_PORT", "8084"))
MANAGER_HOST = os.getenv("LOCAL_LLM_HOST", "0.0.0.0")
MANAGER_PORT = int(os.getenv("LOCAL_LLM_PORT", "8083"))
INTERNAL_TOKEN = os.getenv("SCANNER_INTERNAL_TOKEN", "")
ALIAS = os.getenv("LOCAL_LLM_ALIAS", "qwen3.6-27b")
CTX_SIZE = int(os.getenv("LOCAL_LLM_CTX", "8192"))


def load_definition() -> dict:
    if DEFINITION_PATH.exists():
        return json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    return {
        "id": ALIAS,
        "filename": "Qwen3.6-27B-UD-Q4_K_XL.gguf",
        "download_url": "https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/resolve/main/Qwen3.6-27B-UD-Q4_K_XL.gguf",
        "sha256": "ff6941ded525b34eb159496762c29dd0ec6e71dc31b74d57e75d871a03eec259",
        "size_bytes": 17612564704,
        "context_length": CTX_SIZE,
        "license": "Apache-2.0",
        "quant": "UD-Q4_K_XL",
        "recommended_ram_gb": 24,
        "recommended_vram_gb": 18,
        "display_name": "Qwen3.6 27B (Unsloth Q4)",
        "repo_id": "unsloth/Qwen3.6-27B-GGUF",
    }


def model_path(definition: dict | None = None) -> Path:
    spec = definition or load_definition()
    return MODELS_DIR / str(spec.get("filename") or "model.gguf")
