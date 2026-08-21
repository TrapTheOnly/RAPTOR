# Phase 4 — Multi-provider AI scanner

Engineering spec for RAPTOR’s LLM provider catalog, Operator Console AI Settings, and the bundled Unsloth Qwen3.6-27B local runtime. This is not an in-app docs portal article.

**Status:** implemented  
**Depends on:** existing scanner sidecar, MCP, Kali, `scanner_config` policy, Phase 2b env scan ceilings. Schema migration is `0024_llm_connections.py`.  
**Non-goals:** per-scan model picker in the wave UI, shipping GGUF weights in the image, vision / mmproj, 256k context, extra quants, Entra ID / OCI instance-principal.

## Goal

Replace the Bedrock-only scanner configuration with a catalog of API providers (Anthropic, OpenAI, Gemini, Kimi, Qwen, DeepSeek, Bedrock, Azure OpenAI, Oracle Generative AI, custom OpenAI/Anthropic-compatible) plus an optional on-device GGUF. One active model drives `launch-scan`. Credentials live in Admin Settings, Fernet-encrypted.

## Frozen rules

- Two wire protocols only: Anthropic Messages and OpenAI Chat Completions + tools. No LiteLLM gateway.
- Many saved connections, one `scanner_config.active_connection_id` + `active_model_id`.
- GET never returns secrets. Mask is `••••••••`.
- The local connection (`type=local`) is built-in and cannot be created or deleted by the admin.
- Weights for `unsloth/Qwen3.6-27B-GGUF` `Qwen3.6-27B-UD-Q4_K_XL.gguf` (~17.6 GB, sha256 `ff6941ded525b34eb159496762c29dd0ec6e71dc31b74d57e75d871a03eec259`) download on demand into the `llm_models` volume.
- `local-llm` starts with the scanner stack (`--with-scanner`). The manager stays up even if the GGUF is missing.
- Launch still requires an open, started wave, global/env concurrency, and the existing destructive AND.
- A scan is one job per wave. Flask `POST /api/apps/:id/waves/:waveId/launch-scan` collects every in-scope host and posts `record_ids` + `hosts` to `scanner:8082`. Per-host `POST /pentest/:id/launch-scan` returns 400.
- Kali is not used from Flask. The scanner sidecar talks to RAPTOR MCP over HTTP (`http://mcp:8081/mcp`) and to Kali MCP over stdio (`python3 $KALI_CLIENT_PATH --server http://kali:5000`). Start those sidecars with `./scripts/docker_runner.sh --with-scanner --build`. `--no-scanner` leaves Kali, scanner, and local-llm down; dispatch then returns 502 with that command in the error.
- Claude thinking and prompt cache stay on the Anthropic adapter; other providers no-op them.
- Local scans are $0 and abort on `max_turns`.

## Schema

`llm_connections`: `type`, `display_name`, JSON `config` / `models`, `enabled`, `last_checked_at`, `last_error`. Unique: at most one `type=local`.

`scanner_config` adds `active_connection_id`, `active_model_id`, `thinking_budget_tokens` (default 8000), `max_turns` (default 40). Existing `bedrock_model_id` is migrated into a Bedrock connection when set.

## Runtime

- Flask talks to `scanner:8082` with a provider-neutral job body.
- Scanner `scanner/llm/` builds `AnthropicMessagesClient` or `OpenAIChatClient`.
- Local inference is `http://local-llm:8084/v1` via llama-server; the manager API is `:8083`.

## Admin UI

Settings → AI Scanner: Connections, Local model, Policy. Operator Console primitives only.

## Tests

- Backend: `llm_connections` CRUD/masking, catalog refresh mocks, provider-neutral launch body, local status proxy.
- Scanner: Anthropic/OpenAI tool mapping, local jobs without AWS fields, $0 local cost tracker.
- Frontend: Operator Console restyle guard plus Connections / Local / Policy source checks.

