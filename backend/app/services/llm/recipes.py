"""Baked LLM provider recipes for the AI scanner."""

from typing import Any, Dict, List, Optional

PROTOCOL_ANTHROPIC = "anthropic"
PROTOCOL_OPENAI = "openai"

LOCAL_TYPE = "local"
LOCAL_MODEL_ID = "qwen3.6-27b"
LOCAL_DISPLAY_NAME = "RAPTOR Local"
LOCAL_MODEL_LABEL = "Qwen3.6 27B (Unsloth Q4)"

USER_CREATABLE_TYPES = (
    "anthropic",
    "openai",
    "gemini",
    "kimi",
    "qwen",
    "deepseek",
    "bedrock",
    "azure",
    "oracle",
    "openai_compat",
    "anthropic_compat",
)

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "label": "Anthropic",
        "protocol": PROTOCOL_ANTHROPIC,
        "default_base_url": "https://api.anthropic.com",
        "auth": "x-api-key",
        "list_path": "/v1/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key",),
        "thinking": True,
        "cache": True,
        "suggested_models": [
            {"id": "claude-sonnet-4-5", "display_name": "Claude Sonnet 4.5", "input_cost_per_1m": 3.0, "output_cost_per_1m": 15.0},
            {"id": "claude-opus-4-5", "display_name": "Claude Opus 4.5", "input_cost_per_1m": 5.0, "output_cost_per_1m": 25.0},
            {"id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "input_cost_per_1m": 1.0, "output_cost_per_1m": 5.0},
        ],
    },
    "openai": {
        "label": "OpenAI",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "https://api.openai.com/v1",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key",),
        "suggested_models": [
            {"id": "gpt-5", "display_name": "GPT-5"},
            {"id": "gpt-4.1", "display_name": "GPT-4.1", "input_cost_per_1m": 2.0, "output_cost_per_1m": 8.0},
        ],
    },
    "gemini": {
        "label": "Google Gemini",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key",),
        "suggested_models": [
            {"id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro"},
            {"id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash"},
        ],
    },
    "kimi": {
        "label": "Kimi (Moonshot)",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "https://api.moonshot.ai/v1",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key",),
        "config_fields": ("base_url",),
        "suggested_models": [
            {"id": "kimi-k2.5", "display_name": "Kimi K2.5"},
            {"id": "moonshot-v1-auto", "display_name": "Moonshot V1 Auto"},
        ],
    },
    "qwen": {
        "label": "Qwen (DashScope)",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key",),
        "config_fields": ("base_url",),
        "suggested_models": [
            {"id": "qwen-max", "display_name": "Qwen Max"},
            {"id": "qwen-plus", "display_name": "Qwen Plus"},
            {"id": "qwen3-max", "display_name": "Qwen3 Max"},
        ],
    },
    "deepseek": {
        "label": "DeepSeek",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "https://api.deepseek.com",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key",),
        "suggested_models": [
            {"id": "deepseek-chat", "display_name": "DeepSeek Chat"},
            {"id": "deepseek-reasoner", "display_name": "DeepSeek Reasoner"},
        ],
    },
    "bedrock": {
        "label": "AWS Bedrock",
        "protocol": PROTOCOL_ANTHROPIC,
        "default_base_url": "",
        "auth": "bedrock",
        "list_path": "",
        "catalog": True,
        "secret_fields": ("aws_bearer_token", "aws_secret_access_key", "aws_session_token"),
        "required_on_create": (),
        "config_fields": ("aws_region", "access_key_id", "aws_bearer_token"),
        "thinking": True,
        "cache": True,
        "suggested_models": [
            {
                "id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
                "display_name": "Claude Sonnet 4.5 (Bedrock)",
            },
        ],
    },
    "azure": {
        "label": "Azure OpenAI",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "",
        "auth": "azure",
        "list_path": "/openai/deployments",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key", "endpoint"),
        "config_fields": ("endpoint", "api_version"),
        "suggested_models": [],
    },
    "oracle": {
        "label": "Oracle Generative AI",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("api_key", "region"),
        "config_fields": ("region", "project_ocid", "base_url"),
        "suggested_models": [],
    },
    "openai_compat": {
        "label": "Custom OpenAI-compatible",
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "",
        "auth": "bearer",
        "list_path": "/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("base_url",),
        "config_fields": ("base_url",),
        "suggested_models": [],
    },
    "anthropic_compat": {
        "label": "Custom Anthropic-compatible",
        "protocol": PROTOCOL_ANTHROPIC,
        "default_base_url": "",
        "auth": "x-api-key",
        "list_path": "/v1/models",
        "catalog": True,
        "secret_fields": ("api_key",),
        "required_on_create": ("base_url", "api_key"),
        "config_fields": ("base_url",),
        "thinking": True,
        "suggested_models": [],
    },
    "local": {
        "label": LOCAL_DISPLAY_NAME,
        "protocol": PROTOCOL_OPENAI,
        "default_base_url": "http://local-llm:8084/v1",
        "auth": "none",
        "list_path": "",
        "catalog": False,
        "secret_fields": (),
        "required_on_create": (),
        "thinking": False,
        "cache": False,
        "suggested_models": [
            {"id": LOCAL_MODEL_ID, "display_name": LOCAL_MODEL_LABEL},
        ],
    },
}


def recipe_for(provider_type: str) -> Optional[Dict[str, Any]]:
    return PROVIDERS.get(str(provider_type or "").strip().lower())


def type_label(provider_type: str) -> str:
    recipe = recipe_for(provider_type)
    return str((recipe or {}).get("label") or provider_type)


def secret_fields_for(provider_type: str) -> List[str]:
    recipe = recipe_for(provider_type) or {}
    return list(recipe.get("secret_fields") or ())


def oracle_base_url(region: str) -> str:
    cleaned = str(region or "us-chicago-1").strip() or "us-chicago-1"
    return f"https://inference.generativeai.{cleaned}.oci.oraclecloud.com/openai/v1"


def resolve_base_url(provider_type: str, config: Optional[Dict[str, Any]] = None) -> str:
    kind = str(provider_type or "").strip().lower()
    cfg = dict(config or {})
    explicit = str(cfg.get("base_url") or "").strip().rstrip("/")
    recipe = recipe_for(kind) or {}
    if kind == "azure":
        endpoint = str(cfg.get("endpoint") or explicit).strip().rstrip("/")
        return endpoint
    if kind == "oracle":
        if explicit:
            return explicit
        return oracle_base_url(str(cfg.get("region") or ""))
    if kind == "local":
        return str(recipe.get("default_base_url") or "http://local-llm:8084/v1")
    if explicit:
        return explicit
    return str(recipe.get("default_base_url") or "").rstrip("/")


def default_local_models() -> List[Dict[str, Any]]:
    return [
        {
            "id": LOCAL_MODEL_ID,
            "display_name": LOCAL_MODEL_LABEL,
            "source": "bundled",
            "selected": True,
            "tools": True,
            "thinking": False,
            "input_cost_per_1m": 0,
            "output_cost_per_1m": 0,
        }
    ]


__all__ = [
    "LOCAL_DISPLAY_NAME",
    "LOCAL_MODEL_ID",
    "LOCAL_MODEL_LABEL",
    "LOCAL_TYPE",
    "PROTOCOL_ANTHROPIC",
    "PROTOCOL_OPENAI",
    "PROVIDERS",
    "USER_CREATABLE_TYPES",
    "default_local_models",
    "oracle_base_url",
    "recipe_for",
    "resolve_base_url",
    "secret_fields_for",
    "type_label",
]
